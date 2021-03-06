/*******************************************************************************
 * StockD fetches EOD stock market data from Offical Stock exchange sites
 *     Copyright (C) 2020  Viresh Gupta
 *     More at https://github.com/virresh/StockD/
 * 
 *     This program is free software; you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation; either version 2 of the License, or
 *     (at your option) any later version.
 * 
 *     This program is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 * 
 *     You should have received a copy of the GNU General Public License along
 *     with this program; if not, write to the Free Software Foundation, Inc.,
 *     51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 ******************************************************************************/
package models;

import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

import org.sql2o.Sql2oException;

import common.Queries;
import common.RunContext;
import db.DBConnection;
import main.FxApp;

public class ConfigurationWrapper {
	private List<Setting> all_settings;
	private List<Link> all_links;
	private List<BaseLink> base_links;
	private static ConfigurationWrapper instance;
	private static Logger logger = Logger.getLogger(Logger.GLOBAL_LOGGER_NAME);
	
	public List<Setting> get_all_settings(){
		return all_settings;
	}
	
	public List<Link> get_all_links(){
		return all_links;
	}
	
	public List<BaseLink> get_base_links(){
		return base_links;
	}
	
	private ConfigurationWrapper() {
		all_settings = new ArrayList<Setting>();
		all_links = new ArrayList<Link>();
		base_links = new ArrayList<BaseLink>();
	}
	
	public void add_setting(Setting s) {
		all_settings.add(s);
	}

	public void add_link(Link s) {
		all_links.add(s);
	}

	public void add_baselink(BaseLink s) {
		base_links.add(s);
	}

	public void update_all_settings(List<Setting> s) {
		all_settings = s;
		RunContext.getContext().updateContext();
	}

	public void update_all_links(List<Link> s) {
		all_links = s;
		RunContext.getContext().updateContext();
	}

	public void update_all_baselinks(List<BaseLink> s) {
		base_links = s;
		RunContext.getContext().updateContext();
	}
	
	
	public void override_and_save_to_db() throws SQLException {
		if(all_settings != null) {
			for(Setting s: all_settings) {
				try {					
					DBConnection.getConnection().createQuery(Queries.insertSetting()).bind(s).executeUpdate();
				}
				catch(Sql2oException ex) {
					if(ex.getMessage().contains("duplicate key")) {
						DBConnection.getConnection().createQuery(Queries.updateSetting()).bind(s).executeUpdate();
					}
				}
			}
		}
		if(base_links != null) {
			for(BaseLink s: base_links) {
				try {					
					DBConnection.getConnection().createQuery(Queries.insertBaseLink()).bind(s).executeUpdate();
				}
				catch(Sql2oException ex) {
					if(ex.getMessage().contains("duplicate key")) {
						DBConnection.getConnection().createQuery(Queries.updateBaseLink()).bind(s).executeUpdate();
					}
				}
			}
		}
		if(all_links != null) {
			for(Link s: all_links) {
				try {					
					DBConnection.getConnection().createQuery(Queries.insertLink()).bind(s).executeUpdate();
				}
				catch(Sql2oException ex) {
					if(ex.getMessage().contains("duplicate key")) {
						DBConnection.getConnection().createQuery(Queries.updateLink()).bind(s).executeUpdate();
					}
				}
			}
		}
		logger.log(Level.INFO, "All settings updated\n");
		RunContext.getContext().updateContext();
	}
	
	public void load_from_from_db() {
		try {
			update_all_baselinks(
					DBConnection.getConnection()
					.createQuery(Queries.readBaseLinks())
					.executeAndFetch(BaseLink.class)
			);
			
			update_all_links(
					DBConnection.getConnection()
					.createQuery(Queries.readNormalLinks())
					.executeAndFetch(Link.class)
			);

			update_all_settings(
					DBConnection.getConnection()
					.createQuery(Queries.readSettings())
					.executeAndFetch(Setting.class)
			);
		}
		catch (SQLException e) {
			e.printStackTrace();
			logger.log(Level.SEVERE, e.getMessage());
		}
		RunContext.getContext().updateContext();
	}
	
	public static ConfigurationWrapper getInstance(boolean skipcheck) {
		if(instance != null) {
			return instance;
		}
		else {
			instance = new ConfigurationWrapper();
			instance.load_from_from_db();
			if(instance.base_links.size() == 0 && !skipcheck) {
				FxApp.firstTimeLoad();
			}
			return instance;
		}
	}
	
	public static ConfigurationWrapper getInstance() {
		return getInstance(false);
	}
}
