# Wiseled_LBR UI

A Streamlit-based control interface for the Wiseled_LBR illuminator system.

## Overview

The Wiseled_LBR UI is a software application that provides an intuitive interface to control, monitor, and configure the Wiseled lamp system via serial communication. It implements the requirements specified in the Wiseled_LBR.UI Requirements document.

## Features

- **Light Control**: Adjust individual and master intensity for the three light sources
- **Real-time Monitoring**: Display current and temperature readings with visual alerts
- **Historical Data**: Track and visualize sensor readings over time
- **Error Management**: View and manage error logs with recovery suggestions
- **Customization**: Configure light names, thresholds, and UI appearance
- **Preset Management**: Save and recall lighting configurations

## Requirements

- Python 3.7 or higher
- Streamlit
- PySerial
- Pandas
- Altair
- NumPy

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/wiseled-lbr-ui.git
   cd wiseled-lbr-ui
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the Streamlit application:
   ```
   streamlit run app.py
   ```

2. Connect to your Wiseled_LBR illuminator:
   - Go to the Settings tab
   - Select the correct serial port and baud rate (default: 115200)
   - Click "Connect"

3. Control the lights:
   - Use individual sliders to control each light source
   - Use the master slider to control all light sources simultaneously
   - Create and load presets for quick access to commonly used configurations

4. Monitor the system:
   - View real-time current and temperature readings
   - Check historical data visualizations
   - Export data for external analysis

5. Manage errors:
   - View and clear error logs
   - Receive alerts for warning and critical conditions
   - Follow recovery suggestions for common error conditions

## Project Structure

- `app.py` - Main Streamlit application
- `serial_comm.py` - Serial communication module
- `requirements.txt` - Required Python packages
- `wiseled_settings.json` - User settings (generated on first save)

## Customization

The UI can be customized in several ways:

- **Light Names**: Change the names of the three light sources
- **Warning/Critical Thresholds**: Configure when to show warnings or critical alerts
- **UI Theme**: Choose between light and dark themes
- **Presets**: Save and load custom lighting configurations

Settings are automatically saved to `wiseled_settings.json` when you click "Save Settings".

## Development

### Serial Protocol

The UI communicates with the Wiseled_LBR illuminator using a JSON-based serial protocol. Each message follows this format:

```json
{
  "type": "cmd|resp|event",
  "id": "unique-message-id",
  "topic": "light|status|system|alarm",
  "action": "specific-action",
  "data": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

For details, see the protocol specification in the Wiseled_LBR REQ-COMM-001 document.

### Adding Features

To extend the UI:

1. Add new UI elements in the appropriate section of `app.py`
2. Implement new communication commands in `serial_comm.py` if needed
3. Update the session state to store new settings or data
4. Add new visualization components if required

## Troubleshooting

- **Connection Issues**: Ensure the correct port and baud rate are selected
- **Data Not Updating**: Check the "Auto Refresh" setting is enabled
- **Missing Visualization**: Ensure historical data exists (operate the system for a while)
- **UI Not Responsive**: Check system resources and reduce update frequency if needed

## License

This software is proprietary and confidential. All rights reserved.

## Support

For issues or questions, please contact [support@example.com](mailto:support@example.com).
