from app import app
from flask import render_template, abort, jsonify
from flask import request, Response, g
import json
import time
import os
import queue
import requests
import io
import zipfile
import pandas as pd
import datetime
import traceback
from multiprocessing.managers import BaseManager

eventQ = queue.Queue(maxsize=100)

def getQ():
    # if not hasattr(g, 'eventQ'):
    #     # manager = BaseManager(('', 37844), b'password')
    #     # manager.register('get_Q')
    #     # manager.connect()
    #     g.eventQ = queue.Queue(maxsize=100)
    return eventQ

def attachToStream():
    while True:
        item = getQ().get()
        print(item)
        yield "event: {}\ndata: {}\n\n".format(item['event'], item['data'])

def get_csv(weblink):
    headers = {
        'user-agent': 'Python Client'
    }
    r = requests.get(weblink, headers=headers)
    if r.status_code != 200:
        return None

    if 'zip' not in r.headers.get('Content-Type', ''):
        csvBytes = r.content
    else:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        csvBytes = z.read(z.namelist()[0])

    df = pd.read_csv(io.BytesIO(csvBytes), dtype=str)
    return df

def process_eq(weblink, saveloc, d):
    df = get_csv(weblink)
    df = df[df['SERIES'].isin(['EQ', 'BE'])]
    cname_map = {
        'TOTTRDQTY': 'VOLUME'
    }
    df = df.rename(columns=cname_map)
    df['DATE'] = [d.strftime('%Y%m%d')] * len(df)
    df['OI'] = ['0.0'] * len(df)
    df = df[['SYMBOL', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'OI']]
    df.to_csv(saveloc, header=None, index=None)
    return df


def process_fu(weblink, saveloc, d, asPrefix=False):
    df = get_csv(weblink)
    df = df[df['INSTRUMENT'].isin(['FUTIDX', 'FUTSTK'])]

    last_symbol = None
    prefix = 'I'
    for i, row in df.iterrows():
        if last_symbol is None:
            last_symbol = row['SYMBOL']
        elif last_symbol == row['SYMBOL']:
            prefix += 'I'
        else:
            last_symbol = row['SYMBOL']
            prefix = 'I'
        if asPrefix:
            row['SYMBOL'] = prefix + '-' + row['SYMBOL']
        else:
            row['SYMBOL'] = row['SYMBOL'] + '-' + prefix

    cname_map = {
        'VAL_INLAKH': 'VOLUME',
        'OPEN_INT': 'OI'
    }
    df = df.rename(columns=cname_map)
    df['DATE'] = [d.strftime('%Y%m%d')] * len(df)
    df = df[['SYMBOL', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'OI']]
    df.to_csv(saveloc, header=None, index=None)
    return df


def process_in(weblink, saveloc, d):
    df = get_csv(weblink)
    df = df.replace('-', '0.0')

    cname_map = {
        'Index Name': 'SYMBOL',
        'Open Index Value': 'OPEN',
        'High Index Value': 'HIGH',
        'Low Index Value': 'LOW',
        'Closing Index Value': 'CLOSE',
        'Volume': 'VOLUME'
    }
    df = df.rename(columns=cname_map)
    df['DATE'] = [d.strftime('%Y%m%d')] * len(df)
    df['OI'] = ['0.0'] * len(df)
    df = df[['SYMBOL', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'OI']]
    df['SYMBOL'] = df['SYMBOL'].apply(lambda x: x.replace(' ', '_'))
    df.to_csv(saveloc, header=None, index=None)
    return df

def process_day(configs, date):
    eqdf = None
    fudf = None
    indf = None
    getQ().put({'event': 'log', 'data': date.strftime('Processing %Y-%b-%d')})
    if configs['SETTINGS']['advSkipWeekend']['value'] == 'true' and date.weekday() >= 5:
        getQ().put({'event': 'log', 'data': date.strftime('Skipping Weekend %Y-%b-%d')})
    else:
        if configs['SETTINGS']['eqCheck']['value'] == 'true':
            try:
                eqlink = date.strftime(configs['LINKS']['eqBhav']['link'])
                eqlocation = os.path.join(configs['SETTINGS']['eqDir']['value'], date.strftime('EQ_%Y%^b%d.txt'))
                if not os.path.exists(configs['SETTINGS']['eqDir']['value']):
                    os.makedirs(configs['SETTINGS']['eqDir']['value'], exist_ok=True)
                eqdf = process_eq(eqlink, eqlocation, date)
            except:
                getQ().put({'event': 'log', 'data': date.strftime('Cannot Find EQ Bhavcopy for %Y-%b-%d')})

        if configs['SETTINGS']['fuCheck']['value'] == 'true':
            try:
                fulink = date.strftime(configs['LINKS']['fuBhav']['link'])
                fulocation = os.path.join(configs['SETTINGS']['fuDir']['value'], date.strftime('FU_%Y%^b%d.txt'))
                if not os.path.exists(configs['SETTINGS']['fuDir']['value']):
                    os.makedirs(configs['SETTINGS']['fuDir']['value'], exist_ok=True)
                fudf = process_fu(fulink, fulocation, date)
            except:
                getQ().put({'event': 'log', 'data': date.strftime('Cannot Find FU Bhavcopy for %Y-%b-%d')})

        if configs['SETTINGS']['inCheck']['value'] == 'true':
            try:
                inlink = date.strftime(configs['LINKS']['indall']['link'])
                inlocation = os.path.join(configs['SETTINGS']['inDir']['value'], date.strftime('IN_%Y%^b%d.txt'))
                if not os.path.exists(configs['SETTINGS']['inDir']['value']):
                    os.makedirs(configs['SETTINGS']['inDir']['value'], exist_ok=True)
                indf = process_in(inlink, inlocation, date)
            except:
                getQ().put({'event': 'log', 'data': date.strftime('Cannot Find IN Bhavcopy for %Y-%b-%d')})

        if configs['SETTINGS']['allCheck']['value'] == 'true':
            try:
                alllocation = os.path.join(configs['SETTINGS']['allDir']['value'], date.strftime('ALL_%Y%^b%d.txt'))
                alldf = pd.concat([eqdf, fudf, indf])
                if not os.path.exists(configs['SETTINGS']['allDir']['value']):
                    os.makedirs(configs['SETTINGS']['allDir']['value'], exist_ok=True)
                alldf.to_csv(alllocation, header=False, index=False)
            except Exception as err:
                traceback.print_exception(type(err), err, err.__traceback__)
                getQ().put({'event': 'log', 'data': date.strftime('Cannot consolidate for %Y-%b-%d')})
    getQ().put({'event': 'log', 'data': date.strftime('Done with %Y-%b-%d')})


@app.route('/download', methods=['POST'])
def process_range():
    done_days = 0
    try:
        start = datetime.datetime.strptime(request.form['fromDate'], '%Y-%m-%d')
        end = datetime.datetime.strptime(request.form['toDate'], '%Y-%m-%d')
        print(start, end)
        if not os.path.exists('./default_config.json'):
            getQ().put({'event': 'progress', 'data': '-1'})
            return

        with open('./default_config.json', 'r') as f:
            main_config = json.load(f)

        if os.path.exists('./generate_config.json'):
            with open('./generate_config.json', 'r') as f:
                aux_config = json.load(f)
                main_config.update(aux_config)

        getQ().put({'event': 'progress', 'data': '0'})
        delta = datetime.timedelta(1)
        total_range = end - start + delta
        cur_day = start
        for day in range(0, total_range.days):
            process_day(main_config, cur_day)
            cur_day = cur_day + delta
            getQ().put({'event': 'progress', 'data': str(int(((day+1) / total_range.days) * 100))})
            done_days += 1
    except Exception as ex:
        print(ex)
        getQ().put({'event': 'progress', 'data': '-1'})

    return "Downloaded {} days".format(done_days)

@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/version')
def version():
    return "4.1"

@app.route('/test', methods=['POST'])
def test():
    d = request.form
    print(d)
    return json.dumps(d)

@app.route('/addToQueue/<datapackage>', methods=['GET'])
def qadder(datapackage):
    getQ().put({'event': 'message', 'data': datapackage})
    return "Currently " + str(getQ().qsize()) + " events."

@app.route('/getConfig', methods=['GET'])
def getConfig():
    if not os.path.exists('./default_config.json'):
        abort(404)

    with open('./default_config.json', 'r') as f:
        main_config = json.load(f)

    if os.path.exists('./generate_config.json'):
        with open('./generate_config.json', 'r') as f:
            aux_config = json.load(f)
            main_config.update(aux_config)

    return jsonify(main_config)

@app.route('/setConfig', methods=['POST'])
def saveConfig():
    if not os.path.exists('./default_config.json'):
        abort(404)

    with open('./default_config.json', 'r') as f:
        main_config = json.load(f)

    if os.path.exists('./generate_config.json'):
        with open('./generate_config.json', 'r') as f:
            aux_config = json.load(f)
            main_config.update(aux_config)

    if(not request.is_json):
        d = request.form
        print(d)

        for key in main_config['SETTINGS']:
            if key in d:
                main_config['SETTINGS'][key]['value'] = d[key]
    else:
        d = request.get_json()
        print(d)

        if "BASELINK" in d:
            main_config["BASELINK"].update(d["BASELINK"])

        if "LINKS" in d:
            main_config["LINKS"].update(d["LINKS"])

    with open('./generate_config.json', 'w') as f:
        json.dump(main_config, f)

    return 'Setting Update Succesful'


"""
Stream is supposed provide three events:
- message
- log
- progress
"""
@app.route('/stream')
def getstream():
    m = "";
    main_config = None
    if not os.path.exists('./default_config.json'):
        m = "Configuration files missing!"
    else:
        with open('./default_config.json', 'r') as f:
            main_config = json.load(f)

        if os.path.exists('./generate_config.json'):
            with open('./generate_config.json', 'r') as f:
                aux_config = json.load(f)
                main_config.update(aux_config)

    if main_config is not None:
        vlink = main_config["LINKS"]["version"]['link']
        r = requests.get(vlink)
        if r.status_code != 200:
            m = "Cannot connect to internet! StockD requires internet to function! If you are sure you have internet connectivity, then report this and proceed with download."
        else:
            latest_v = float(r.content.decode('UTF-8-sig'))
            cur_v = float(version())
            if cur_v < latest_v:
                m = "An update is available! Please update to latest version for best performance."
            else:
                m = ""
    getQ().put({'event': 'message', 'data': m})
    return Response(attachToStream(),
                    mimetype='text/event-stream')
