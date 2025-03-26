#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wiseled_LBR.UI - Serial Communication Module
This module handles serial communication with the Wiseled_LBR illuminator hardware.
"""

import json
import time
import logging
import threading
import queue
import serial
import serial.tools.list_ports
from typing import Dict, List, Callable, Optional, Union, Any

# Configure logger
logger = logging.getLogger(__name__)

class WiseledCommunicator:
    """Handles communication with the Wiseled_LBR illuminator hardware."""
    
    def __init__(self):
        self.serial_port = None
        self.port_name = ""
        self.baud_rate = 115200
        self.connected = False
        self.running = False
        self.message_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.event_callbacks = []
        self.response_callbacks = {}
        self.command_id_counter = 1
        self.receive_thread = None
        self.process_thread = None
        self.buffer = ""
        
    def list_ports(self) -> List[str]:
        """List available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def connect(self, port: str, baud_rate: int = 115200) -> bool:
        """Connect to the device on the specified port."""
        try:
            # Check if already connected
            if self.connected:
                self.disconnect()
            
            # Open serial port
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            
            # Set parameters
            self.port_name = port
            self.baud_rate = baud_rate
            self.connected = True
            self.running = True
            
            # Start threads
            self.receive_thread = threading.Thread(target=self._receive_thread, daemon=True)
            self.process_thread = threading.Thread(target=self._process_thread, daemon=True)
            self.receive_thread.start()
            self.process_thread.start()
            
            # Send ping to verify connection
            response = self.send_command("system", "ping", {})
            if response and response.get("data", {}).get("status") == "ok":
                logger.info(f"Connected to {port} at {baud_rate} baud")
                return True
            else:
                self.disconnect()
                return False
            
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            self.disconnect()
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from the device."""
        self.running = False
        
        if self.receive_thread:
            if self.receive_thread.is_alive():
                self.receive_thread.join(timeout=1.0)
            self.receive_thread = None
            
        if self.process_thread:
            if self.process_thread.is_alive():
                self.process_thread.join(timeout=1.0)
            self.process_thread = None
        
        if self.serial_port:
            try:
                self.serial_port.close()
            except Exception as e:
                logger.error(f"Error closing serial port: {str(e)}")
        
        self.serial_port = None
        self.connected = False
        logger.info("Disconnected from device")
        return True
    
    def is_connected(self) -> bool:
        """Check if the device is connected."""
        return self.connected
    
    def get_port(self) -> str:
        """Get the current port name."""
        return self.port_name
    
    def get_baud_rate(self) -> int:
        """Get the current baud rate."""
        return self.baud_rate
    
    def send_command(self, topic: str, action: str, data: Dict[str, Any], 
                    timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """Send a command to the device and wait for a response."""
        if not self.connected:
            logger.error("Cannot send command: Not connected")
            return None
        
        # Create command ID
        cmd_id = f"cmd-{self.command_id_counter}"
        self.command_id_counter += 1
        
        # Create command
        command = {
            "type": "cmd",
            "id": cmd_id,
            "topic": topic,
            "action": action,
            "data": data
        }
        
        # Create response event
        response_event = threading.Event()
        response = [None]  # Use a list to allow modification in callback
        
        # Create callback
        def response_callback(resp):
            response[0] = resp
            response_event.set()
        
        # Register callback
        self.response_callbacks[cmd_id] = response_callback
        
        try:
            # Send command
            command_str = json.dumps(command) + "\n"
            self.serial_port.write(command_str.encode('utf-8'))
            logger.debug(f"Sent command: {command_str.strip()}")
            
            # Wait for response with timeout
            if response_event.wait(timeout):
                return response[0]
            else:
                logger.warning(f"Command timed out: {topic}/{action}")
                return None
        
        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return None
        
        finally:
            # Remove callback
            if cmd_id in self.response_callbacks:
                del self.response_callbacks[cmd_id]
    
    def register_event_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for event messages."""
        if callback not in self.event_callbacks:
            self.event_callbacks.append(callback)
    
    def unregister_event_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Unregister an event callback."""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    def _receive_thread(self) -> None:
        """Thread for receiving data from the serial port."""
        logger.debug("Receive thread started")
        
        while self.running and self.connected:
            try:
                if self.serial_port and self.serial_port.is_open:
                    # Read available data
                    data = self.serial_port.read(self.serial_port.in_waiting or 1)
                    
                    if data:
                        # Decode and add to buffer
                        self.buffer += data.decode('utf-8', errors='replace')
                        
                        # Process complete messages
                        while '\n' in self.buffer:
                            # Split at newline
                            line, self.buffer = self.buffer.split('\n', 1)
                            line = line.strip()
                            
                            if line:
                                try:
                                    # Parse JSON
                                    message = json.loads(line)
                                    logger.debug(f"Received message: {line}")
                                    # Add to queue
                                    self.message_queue.put(message)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Invalid JSON: {line} - {str(e)}")
                
                # Small delay to prevent CPU hogging
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in receive thread: {str(e)}")
                time.sleep(0.1)
        
        logger.debug("Receive thread stopped")
    
    def _process_thread(self) -> None:
        """Thread for processing received messages."""
        logger.debug("Process thread started")
        
        while self.running:
            try:
                # Get message from queue with timeout
                try:
                    message = self.message_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Process message based on type
                message_type = message.get("type")
                message_id = message.get("id", "")
                
                if message_type == "resp" and message_id in self.response_callbacks:
                    # Handle response message
                    callback = self.response_callbacks[message_id]
                    callback(message)
                
                elif message_type == "event":
                    # Handle event message
                    for callback in self.event_callbacks:
                        try:
                            callback(message)
                        except Exception as e:
                            logger.error(f"Error in event callback: {str(e)}")
                
                # Mark message as processed
                self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in process thread: {str(e)}")
        
        logger.debug("Process thread stopped")
    
    # Light control commands
    
    def set_light_intensity(self, light_id: int, intensity: int) -> bool:
        """Set the intensity of a specific light."""
        response = self.send_command(
            "light", "set", 
            {"id": light_id, "intensity": intensity}
        )
        return response and response.get("data", {}).get("status") == "ok"
    
    def set_all_light_intensities(self, intensities: List[int]) -> bool:
        """Set the intensities of all lights."""
        response = self.send_command(
            "light", "set_all", 
            {"intensities": intensities}
        )
        return response and response.get("data", {}).get("status") == "ok"
    
    def get_light_intensity(self, light_id: int) -> Optional[int]:
        """Get the intensity of a specific light."""
        response = self.send_command(
            "light", "get", 
            {"id": light_id}
        )
        if response and response.get("data", {}).get("status") == "ok":
            return response.get("data", {}).get("intensity")
        return None
    
    def get_all_light_intensities(self) -> Optional[List[int]]:
        """Get the intensities of all lights."""
        response = self.send_command(
            "light", "get_all", 
            {}
        )
        if response and response.get("data", {}).get("status") == "ok":
            return response.get("data", {}).get("intensities")
        return None
    
    # Sensor data commands
    
    def get_light_sensor_data(self, light_id: int) -> Optional[Dict[str, Any]]:
        """Get sensor data for a specific light."""
        response = self.send_command(
            "status", "get_sensors", 
            {"id": light_id}
        )
        if response and response.get("data", {}).get("status") == "ok":
            return response.get("data", {}).get("sensor")
        return None
    
    def get_all_sensor_data(self) -> Optional[List[Dict[str, Any]]]:
        """Get sensor data for all lights."""
        response = self.send_command(
            "status", "get_all_sensors", 
            {}
        )
        if response and response.get("data", {}).get("status") == "ok":
            return response.get("data", {}).get("sensors")
        return None
    
    # Alarm commands
    
    def get_alarm_status(self) -> Optional[List[Dict[str, Any]]]:
        """Get the current alarm status."""
        response = self.send_command(
            "alarm", "status", 
            {}
        )
        if response and response.get("data", {}).get("status") == "ok":
            return response.get("data", {}).get("active_alarms", [])
        return None
    
    def clear_alarm(self, light_id: int) -> bool:
        """Clear the alarm for a specific light."""
        response = self.send_command(
            "alarm", "clear", 
            {"lights": [light_id]}
        )
        return response and response.get("data", {}).get("status") == "ok"
    
    # System commands
    
    def get_system_info(self) -> Optional[Dict[str, Any]]:
        """Get system information."""
        response = self.send_command(
            "system", "info", 
            {}
        )
        if response and response.get("data", {}).get("status") == "ok":
            return response.get("data")
        return None
    
    def get_error_log(self, count: int = 10) -> Optional[List[Dict[str, Any]]]:
        """Get the error log."""
        response = self.send_command(
            "system", "get_error_log", 
            {"count": count}
        )
        if response and response.get("data", {}).get("status") == "ok":
            return response.get("data", {}).get("errors", [])
        return None
    
    def clear_error_log(self) -> bool:
        """Clear the error log."""
        response = self.send_command(
            "system", "clear_error_log", 
            {}
        )
        return response and response.get("data", {}).get("status") == "ok"
