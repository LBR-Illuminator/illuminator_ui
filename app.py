#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wiseled_LBR.UI - Main Streamlit Application
This is the main entry point for the Wiseled_LBR UI application.
"""

import os
import json
import time
import logging
import threading
import streamlit as st
import pandas as pd
import numpy as np
import serial.tools.list_ports
from datetime import datetime
import altair as alt
from typing import Dict, List, Any

from serial_comm import WiseledCommunicator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("wiseled.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize session state
def init_session_state():
    """Initialize the session state with default values."""
    if 'communicator' not in st.session_state:
        st.session_state.communicator = WiseledCommunicator()
    
    if 'connected' not in st.session_state:
        st.session_state.connected = False
    
    if 'light_intensities' not in st.session_state:
        st.session_state.light_intensities = [0, 0, 0]
    
    if 'sensor_data' not in st.session_state:
        st.session_state.sensor_data = [
            {"id": 1, "current": 0.0, "temperature": 0.0},
            {"id": 2, "current": 0.0, "temperature": 0.0},
            {"id": 3, "current": 0.0, "temperature": 0.0}
        ]
    
    if 'alarm_status' not in st.session_state:
        st.session_state.alarm_status = []
    
    if 'error_log' not in st.session_state:
        st.session_state.error_log = []
    
    if 'system_info' not in st.session_state:
        st.session_state.system_info = {}
    
    if 'historical_data' not in st.session_state:
        st.session_state.historical_data = pd.DataFrame(columns=[
            'timestamp', 'light_id', 'intensity', 'current', 'temperature'
        ])
    
    if 'show_alerts' not in st.session_state:
        st.session_state.show_alerts = True
    
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True
    
    if 'light_names' not in st.session_state:
        st.session_state.light_names = ["White", "Green", "Red"]
    
    if 'presets' not in st.session_state:
        st.session_state.presets = {
            "All Off": [0, 0, 0],
            "All On": [100, 100, 100],
            "White Only": [100, 0, 0],
            "Green Only": [0, 100, 0],
            "Red Only": [0, 0, 100],
            "Medium Brightness": [50, 50, 50]
        }
    
    if 'theme' not in st.session_state:
        st.session_state.theme = "light"
    
    if 'warning_thresholds' not in st.session_state:
        st.session_state.warning_thresholds = {
            'current': 40.0,       # mA
            'temperature': 70.0    # °C
        }
    
    if 'critical_thresholds' not in st.session_state:
        st.session_state.critical_thresholds = {
            'current': 45.0,       # mA
            'temperature': 80.0    # °C
        }
    
    if 'event_log' not in st.session_state:
        st.session_state.event_log = []
    
    if 'comm_log' not in st.session_state:
        st.session_state.comm_log = []

def handle_event(event):
    """Handle events from the device."""
    logger.info(f"Event received: {json.dumps(event)}")
    
    # Add to event log
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.event_log.insert(0, {
        "timestamp": timestamp,
        "event": event
    })
    
    # Handle alarm events
    if event.get("type") == "event" and event.get("topic") == "alarm" and event.get("action") == "triggered":
        data = event.get("data", {})
        source = data.get("source", "unknown")
        code = data.get("code", "unknown")
        value = data.get("value", 0)
        
        # Refresh alarm status
        refresh_alarm_status()
        
        # Display alert
        if st.session_state.show_alerts:
            st.toast(f"ALARM: {source} - {code} ({value})", icon="🚨")

def add_historical_data():
    """Add current state to historical data."""
    timestamp = datetime.now().isoformat()
    new_data = []
    
    for i in range(3):
        light_id = i + 1
        intensity = st.session_state.light_intensities[i]
        current = st.session_state.sensor_data[i]["current"] if i < len(st.session_state.sensor_data) else 0
        temperature = st.session_state.sensor_data[i]["temperature"] if i < len(st.session_state.sensor_data) else 0
        
        new_data.append({
            'timestamp': timestamp,
            'light_id': light_id,
            'intensity': intensity,
            'current': current,
            'temperature': temperature
        })
    
    # Convert to DataFrame and append
    new_df = pd.DataFrame(new_data)
    st.session_state.historical_data = pd.concat([new_df, st.session_state.historical_data]).reset_index(drop=True)
    
    # Keep only the last 1000 records to avoid memory issues
    if len(st.session_state.historical_data) > 1000:
        st.session_state.historical_data = st.session_state.historical_data.iloc[:1000]

def export_historical_data(filename):
    """Export historical data to a CSV file."""
    try:
        st.session_state.historical_data.to_csv(filename, index=False)
        return True
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        return False

def export_error_log(filename):
    """Export error log to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(st.session_state.error_log, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error exporting error log: {str(e)}")
        return False

def connect_to_device():
    """Connect to the selected device."""
    port = st.session_state.selected_port
    baud_rate = st.session_state.selected_baud_rate
    
    if st.session_state.communicator.connect(port, baud_rate):
        st.session_state.connected = True
        
        # Register event handler
        st.session_state.communicator.register_event_callback(handle_event)
        
        # Refresh data
        refresh_all_data()
        
        return True
    
    return False

def disconnect_from_device():
    """Disconnect from the device."""
    if st.session_state.communicator:
        st.session_state.communicator.disconnect()
        st.session_state.connected = False
        return True
    
    return False

def refresh_light_intensities():
    """Refresh light intensities from the device."""
    if not st.session_state.connected:
        return False
    
    intensities = st.session_state.communicator.get_all_light_intensities()
    if intensities is not None:
        st.session_state.light_intensities = intensities
        return True
    
    return False

def refresh_sensor_data():
    """Refresh sensor data from the device."""
    if not st.session_state.connected:
        return False
    
    sensor_data = st.session_state.communicator.get_all_sensor_data()
    if sensor_data is not None:
        st.session_state.sensor_data = sensor_data
        return True
    
    return False

def refresh_alarm_status():
    """Refresh alarm status from the device."""
    if not st.session_state.connected:
        return False
    
    alarm_status = st.session_state.communicator.get_alarm_status()
    if alarm_status is not None:
        st.session_state.alarm_status = alarm_status
        return True
    
    return False

def refresh_error_log():
    """Refresh error log from the device."""
    if not st.session_state.connected:
        return False
    
    error_log = st.session_state.communicator.get_error_log()
    if error_log is not None:
        st.session_state.error_log = error_log
        return True
    
    return False

def refresh_system_info():
    """Refresh system information from the device."""
    if not st.session_state.connected:
        return False
    
    system_info = st.session_state.communicator.get_system_info()
    if system_info is not None:
        st.session_state.system_info = system_info
        return True
    
    return False

def refresh_all_data():
    """Refresh all data from the device."""
    refresh_light_intensities()
    refresh_sensor_data()
    refresh_alarm_status()
    refresh_error_log()
    refresh_system_info()
    add_historical_data()

def set_light_intensity(light_id, intensity):
    """Set the intensity of a specific light."""
    if not st.session_state.connected:
        return False
    
    if st.session_state.communicator.set_light_intensity(light_id, intensity):
        # Update local state
        st.session_state.light_intensities[light_id - 1] = intensity
        return True
    
    return False

def set_all_light_intensities(intensities):
    """Set the intensities of all lights."""
    if not st.session_state.connected:
        return False
    
    if st.session_state.communicator.set_all_light_intensities(intensities):
        # Update local state
        st.session_state.light_intensities = intensities.copy()
        return True
    
    return False

def clear_alarm(light_id):
    """Clear the alarm for a specific light."""
    if not st.session_state.connected:
        return False
    
    if st.session_state.communicator.clear_alarm(light_id):
        # Refresh alarm status
        refresh_alarm_status()
        return True
    
    return False

def save_preset(name, intensities):
    """Save a preset configuration."""
    st.session_state.presets[name] = intensities.copy()
    return True

def load_preset(name):
    """Load a preset configuration."""
    if name in st.session_state.presets:
        intensities = st.session_state.presets[name]
        return set_all_light_intensities(intensities)
    
    return False

def clear_error_log():
    """Clear the error log."""
    if not st.session_state.connected:
        return False
    
    if st.session_state.communicator.clear_error_log():
        # Refresh error log
        refresh_error_log()
        return True
    
    return False

def save_settings():
    """Save settings to a JSON file."""
    try:
        settings = {
            "light_names": st.session_state.light_names,
            "presets": st.session_state.presets,
            "warning_thresholds": st.session_state.warning_thresholds,
            "critical_thresholds": st.session_state.critical_thresholds,
            "theme": st.session_state.theme,
            "show_alerts": st.session_state.show_alerts,
            "auto_refresh": st.session_state.auto_refresh
        }
        
        with open("wiseled_settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        
        return True
    
    except Exception as e:
        logger.error(f"Error saving settings: {str(e)}")
        return False

def load_settings():
    """Load settings from a JSON file."""
    try:
        if os.path.exists("wiseled_settings.json"):
            with open("wiseled_settings.json", "r") as f:
                settings = json.load(f)
            
            # Update session state
            if "light_names" in settings:
                st.session_state.light_names = settings["light_names"]
            
            if "presets" in settings:
                st.session_state.presets = settings["presets"]
            
            if "warning_thresholds" in settings:
                st.session_state.warning_thresholds = settings["warning_thresholds"]
            
            if "critical_thresholds" in settings:
                st.session_state.critical_thresholds = settings["critical_thresholds"]
            
            if "theme" in settings:
                st.session_state.theme = settings["theme"]
            
            if "show_alerts" in settings:
                st.session_state.show_alerts = settings["show_alerts"]
            
            if "auto_refresh" in settings:
                st.session_state.auto_refresh = settings["auto_refresh"]
            
            return True
    
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
    
    return False

def render_dashboard():
    """Render the dashboard tab."""
    st.header("Light Control Dashboard")
    
    # Connection status and refresh button
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.session_state.connected:
            st.success(f"Connected to {st.session_state.communicator.get_port()}")
        else:
            st.error("Not connected")
    
    with col2:
        if st.button("Refresh Data"):
            refresh_all_data()
    
    with col3:
        auto_refresh = st.checkbox("Auto Refresh", value=st.session_state.auto_refresh)
        if auto_refresh != st.session_state.auto_refresh:
            st.session_state.auto_refresh = auto_refresh
            save_settings()
    
    # Master control slider
    st.subheader("Master Control")
    
    def on_master_change():
        intensity = st.session_state.master_intensity
        set_all_light_intensities([intensity, intensity, intensity])
    
    master_intensity = max(st.session_state.light_intensities) if st.session_state.light_intensities else 0
    st.slider("All Lights", 0, 100, master_intensity, 1, 
              key="master_intensity", on_change=on_master_change,
              help="Adjust intensity for all light sources simultaneously")
    
    # Light controls
    st.subheader("Individual Light Controls")
    
    light_cols = st.columns(3)
    for i in range(3):
        light_id = i + 1
        light_name = st.session_state.light_names[i]
        intensity = st.session_state.light_intensities[i]
        
        with light_cols[i]:
            st.write(f"**Light {light_id}: {light_name}**")
            
            # Slider for individual light
            def on_light_change(light_id=light_id):
                intensity = st.session_state[f"light_{light_id}_intensity"]
                set_light_intensity(light_id, intensity)
            
            st.slider(f"Intensity", 0, 100, intensity, 1, 
                      key=f"light_{light_id}_intensity", 
                      on_change=on_light_change)
            
            # Show sensor data
            if i < len(st.session_state.sensor_data):
                sensor = st.session_state.sensor_data[i]
                current = sensor.get("current", 0)
                temperature = sensor.get("temperature", 0)
                
                # Determine warning/critical status
                current_status = "normal"
                if current >= st.session_state.critical_thresholds["current"]:
                    current_status = "critical"
                elif current >= st.session_state.warning_thresholds["current"]:
                    current_status = "warning"
                
                temp_status = "normal"
                if temperature >= st.session_state.critical_thresholds["temperature"]:
                    temp_status = "critical"
                elif temperature >= st.session_state.warning_thresholds["temperature"]:
                    temp_status = "warning"
                
                # Render with appropriate styling
                if current_status == "critical":
                    st.error(f"Current: {current:.1f} mA")
                elif current_status == "warning":
                    st.warning(f"Current: {current:.1f} mA")
                else:
                    st.info(f"Current: {current:.1f} mA")
                
                if temp_status == "critical":
                    st.error(f"Temperature: {temperature:.1f} °C")
                elif temp_status == "warning":
                    st.warning(f"Temperature: {temperature:.1f} °C")
                else:
                    st.info(f"Temperature: {temperature:.1f} °C")
                
                # Show alarm status and clear button if there's an alarm
                has_alarm = False
                for alarm in st.session_state.alarm_status:
                    if alarm.get("light") == light_id:
                        has_alarm = True
                        code = alarm.get("code", "unknown")
                        st.error(f"ALARM: {code}")
                        
                        if st.button(f"Clear Alarm", key=f"clear_alarm_{light_id}"):
                            clear_alarm(light_id)
                
                if not has_alarm:
                    st.success("Status: Normal")
    
    # Presets
    st.subheader("Preset Configurations")
    
    preset_cols = st.columns([3, 1])
    
    with preset_cols[0]:
        preset_names = list(st.session_state.presets.keys())
        selected_preset = st.selectbox("Select Preset", preset_names)
        
        if st.button("Load Preset"):
            if selected_preset:
                load_preset(selected_preset)
    
    with preset_cols[1]:
        new_preset_name = st.text_input("New Preset Name")
        
        if st.button("Save Current"):
            if new_preset_name:
                save_preset(new_preset_name, st.session_state.light_intensities)
                st.success(f"Preset '{new_preset_name}' saved")
    
    # Historical data visualization
    st.subheader("Sensor History")
    
    if not st.session_state.historical_data.empty:
        # Create a DataFrame for plotting
        df = st.session_state.historical_data.copy()
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Select most recent data points (last 50)
        df = df.sort_values('timestamp').groupby('light_id').tail(50)
        
        # Create tabs for different visualizations
        viz_tabs = st.tabs(["Temperature", "Current", "Intensity"])
        
        with viz_tabs[0]:
            # Temperature chart
            temp_chart = alt.Chart(df).mark_line().encode(
                x=alt.X('timestamp:T', title='Time'),
                y=alt.Y('temperature:Q', title='Temperature (°C)'),
                color=alt.Color('light_id:N', title='Light', 
                              scale=alt.Scale(domain=[1, 2, 3], 
                                             range=['#FFFFFF', '#00FF00', '#FF0000']))
            ).properties(
                title='Temperature History',
                width=700,
                height=300
            ).interactive()
            
            st.altair_chart(temp_chart, use_container_width=True)
        
        with viz_tabs[1]:
            # Current chart
            current_chart = alt.Chart(df).mark_line().encode(
                x=alt.X('timestamp:T', title='Time'),
                y=alt.Y('current:Q', title='Current (mA)'),
                color=alt.Color('light_id:N', title='Light',
                              scale=alt.Scale(domain=[1, 2, 3], 
                                             range=['#FFFFFF', '#00FF00', '#FF0000']))
            ).properties(
                title='Current History',
                width=700,
                height=300
            ).interactive()
            
            st.altair_chart(current_chart, use_container_width=True)
        
        with viz_tabs[2]:
            # Intensity chart
            intensity_chart = alt.Chart(df).mark_line().encode(
                x=alt.X('timestamp:T', title='Time'),
                y=alt.Y('intensity:Q', title='Intensity (%)'),
                color=alt.Color('light_id:N', title='Light',
                              scale=alt.Scale(domain=[1, 2, 3], 
                                             range=['#FFFFFF', '#00FF00', '#FF0000']))
            ).properties(
                title='Intensity History',
                width=700,
                height=300
            ).interactive()
            
            st.altair_chart(intensity_chart, use_container_width=True)
        
        # Export button
        if st.button("Export Data"):
            export_path = "wiseled_historical_data.csv"
            if export_historical_data(export_path):
                st.success(f"Data exported to {export_path}")
            else:
                st.error("Failed to export data")

def render_error_log():
    """Render the error log tab."""
    st.header("Error Management")
    
    # Refresh and clear buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Refresh Error Log"):
            refresh_error_log()
    
    with col2:
        if st.button("Clear Error Log"):
            if clear_error_log():
                st.success("Error log cleared")
            else:
                st.error("Failed to clear error log")
    
    # Error log display
    st.subheader("Error Log")
    
    if st.session_state.error_log:
        # Create DataFrame for display
        error_data = []
        for error in st.session_state.error_log:
            timestamp = error.get("timestamp", "")
            code = error.get("code", "")
            source = error.get("source", "")
            value = error.get("value", 0)
            
            error_data.append({
                "Timestamp": timestamp,
                "Code": code,
                "Source": source,
                "Value": value
            })
        
        if error_data:
            error_df = pd.DataFrame(error_data)
            st.dataframe(error_df, use_container_width=True)
            
            # Export button
            if st.button("Export Error Log"):
                export_path = "wiseled_error_log.json"
                if export_error_log(export_path):
                    st.success(f"Error log exported to {export_path}")
                else:
                    st.error("Failed to export error log")
    else:
        st.info("No errors in log")
    
    # Event log display
    st.subheader("Event Log")
    
    if st.session_state.event_log:
        # Create DataFrame for display
        event_data = []
        for event_entry in st.session_state.event_log:
            timestamp = event_entry.get("timestamp", "")
            event = event_entry.get("event", {})
            
            topic = event.get("topic", "")
            action = event.get("action", "")
            data = event.get("data", {})
            
            event_data.append({
                "Timestamp": timestamp,
                "Topic": topic,
                "Action": action,
                "Data": str(data)
            })
        
        if event_data:
            event_df = pd.DataFrame(event_data)
            st.dataframe(event_df, use_container_width=True)
    else:
        st.info("No events in log")
    
    # Recovery suggestions
    st.subheader("Recovery Suggestions")
    
    st.write("""
    **Common Error Conditions and Solutions:**
    
    1. **Over-Current Alarms**
       - Ensure the lamp is not obstructed or overheating
       - Reduce intensity settings if the problem persists
       - Check for proper ventilation around the lamp
    
    2. **Over-Temperature Alarms**
       - Ensure proper cooling and ventilation around the lamp
       - Reduce intensity settings to lower heat generation
       - Allow the lamp to cool down before resuming operation
    
    3. **Communication Errors**
       - Check physical connections between the computer and lamp
       - Verify correct port and baud rate settings
       - Try disconnecting and reconnecting the device
       - Restart the Wiseled lamp if problems persist
    
    4. **System Errors**
       - These may indicate firmware issues - contact support
       - Power cycle the lamp to reset internal state
    """)

def render_settings():
    """Render the settings tab."""
    st.header("Settings")
    
    # Connection settings
    st.subheader("Connection Settings")
    
    ports = st.session_state.communicator.list_ports()
    if not ports:
        ports = ["No ports available"]
    
    baud_rates = [9600, 19200, 38400, 57600, 115200]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_port = st.selectbox("Serial Port", ports, key="selected_port")
    
    with col2:
        selected_baud = st.selectbox("Baud Rate", baud_rates, 
                                     index=baud_rates.index(115200) if 115200 in baud_rates else 0,
                                     key="selected_baud_rate")
    
    with col3:
        if st.session_state.connected:
            if st.button("Disconnect"):
                if disconnect_from_device():
                    st.success("Disconnected")
                else:
                    st.error("Failed to disconnect")
        else:
            if st.button("Connect"):
                if connect_to_device():
                    st.success(f"Connected to {selected_port}")
                else:
                    st.error("Failed to connect")
    
    # Light naming settings
    st.subheader("Light Names")
    
    light_name_cols = st.columns(3)
    for i in range(3):
        with light_name_cols[i]:
            light_name = st.text_input(f"Light {i+1} Name", 
                                      value=st.session_state.light_names[i],
                                      key=f"light_name_{i}")
            
            if light_name != st.session_state.light_names[i]:
                st.session_state.light_names[i] = light_name
    
    # Threshold settings
    st.subheader("Threshold Settings")
    
    threshold_cols = st.columns(2)
    
    with threshold_cols[0]:
        st.write("**Warning Thresholds**")
        
        warning_current = st.number_input("Current Warning (mA)", 
                                         min_value=0.0, max_value=100.0, step=0.5,
                                         value=st.session_state.warning_thresholds["current"],
                                         key="warning_current")
        
        warning_temp = st.number_input("Temperature Warning (°C)", 
                                      min_value=0.0, max_value=150.0, step=0.5,
                                      value=st.session_state.warning_thresholds["temperature"],
                                      key="warning_temperature")
        
        if (warning_current != st.session_state.warning_thresholds["current"] or
            warning_temp != st.session_state.warning_thresholds["temperature"]):
            st.session_state.warning_thresholds["current"] = warning_current
            st.session_state.warning_thresholds["temperature"] = warning_temp
    
    with threshold_cols[1]:
        st.write("**Critical Thresholds**")
        
        critical_current = st.number_input("Current Critical (mA)", 
                                          min_value=0.0, max_value=100.0, step=0.5,
                                          value=st.session_state.critical_thresholds["current"],
                                          key="critical_current")
        
        critical_temp = st.number_input("Temperature Critical (°C)", 
                                       min_value=0.0, max_value=150.0, step=0.5,
                                       value=st.session_state.critical_thresholds["temperature"],
                                       key="critical_temperature")
        
        if (critical_current != st.session_state.critical_thresholds["current"] or
            critical_temp != st.session_state.critical_thresholds["temperature"]):
            st.session_state.critical_thresholds["current"] = critical_current
            st.session_state.critical_thresholds["temperature"] = critical_temp
    
    # UI settings
    st.subheader("UI Settings")
    
    ui_cols = st.columns(2)
    
    with ui_cols[0]:
        theme = st.selectbox("Theme", ["light", "dark"], 
                           index=0 if st.session_state.theme == "light" else 1,
                           key="theme_select")
        
        if theme != st.session_state.theme:
            st.session_state.theme = theme
    
    with ui_cols[1]:
        show_alerts = st.checkbox("Show Alerts", value=st.session_state.show_alerts,
                                 key="show_alerts_checkbox")
        
        if show_alerts != st.session_state.show_alerts:
            st.session_state.show_alerts = show_alerts
    
    # Save/Load settings
    st.subheader("Save/Load Settings")
    
    save_load_cols = st.columns(2)
    
    with save_load_cols[0]:
        if st.button("Save Settings"):
            if save_settings():
                st.success("Settings saved")
            else:
                st.error("Failed to save settings")
    
    with save_load_cols[1]:
        if st.button("Load Settings"):
            if load_settings():
                st.success("Settings loaded")
            else:
                st.error("Failed to load settings or no settings file found")
    
    # System information
    if st.session_state.connected and st.session_state.system_info:
        st.subheader("System Information")
        
        info_cols = st.columns(2)
        
        with info_cols[0]:
            st.write(f"**Device:** {st.session_state.system_info.get('device', 'Unknown')}")
            st.write(f"**Version:** {st.session_state.system_info.get('version', 'Unknown')}")
        
        with info_cols[1]:
            st.write(f"**Uptime:** {st.session_state.system_info.get('uptime', 0)} seconds")
            st.write(f"**Lights:** {st.session_state.system_info.get('lights', 0)}")

def main():
    """Main application function."""
    st.set_page_config(
        page_title="Wiseled_LBR Controller",
        page_icon="💡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Load settings if available
    init_session_state()
    load_settings()
    
    # Set theme
    if st.session_state.theme == "dark":
        st.markdown("""
        <style>
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }
        </style>
        """, unsafe_allow_html=True)
    
    # Title
    st.title("Wiseled_LBR Illuminator Control System")
    
    # Create tabs
    tabs = st.tabs(["Dashboard", "Error Management", "Settings"])
    
    # Render tabs
    with tabs[0]:
        render_dashboard()
    
    with tabs[1]:
        render_error_log()
    
    with tabs[2]:
        render_settings()
    
    # Auto-refresh
    if st.session_state.connected and st.session_state.auto_refresh:
        # Use a placeholder to trigger refresh without full page reloads
        refresh_placeholder = st.empty()
        refresh_time = time.time()
        
        # Check if a second has passed since last refresh
        if time.time() - refresh_time >= 1.0:
            refresh_all_data()
            refresh_time = time.time()
            # Use the placeholder to avoid UI rebuild
            with refresh_placeholder:
                pass

if __name__ == "__main__":
    main()
