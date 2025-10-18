# Shakshuka - Modern Task Management Application

A beautiful, modern task management application inspired by meditation app designs, built with Python Flask and featuring encrypted local storage.

## Features

✨ **Modern UI Design**
- Beautiful gradient backgrounds with soft pink/coral theme
- Glass-morphism effects with backdrop blur
- Smooth animations and transitions
- Responsive design for all screen sizes

📋 **Task Management**
- Create, edit, and delete tasks
- Mark tasks as completed
- Priority levels (High, Medium, Low)
- Task categories (Work, Personal, Health, Learning, etc.)
- Due dates and estimated duration

📅 **Daily Planner**
- Drag-and-drop task scheduling
- Hourly time slots (24-hour view)
- Visual task scheduling interface
- Date navigation

🔒 **Data Security**
- Encrypted local file storage
- Data persists through updates
- Export/import functionality
- Secure data handling

⚙️ **Advanced Features**
- Windows autostart integration
- Auto-save functionality
- Dashboard with productivity stats
- Task completion streaks
- Quick add functionality

## Installation & Usage

### Option 1: Run from Source

1. **Install Python 3.8+** (if not already installed)

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

4. **Open your browser** and navigate to `http://127.0.0.1:8989`

### Option 2: Build Executable

1. **Run the build script:**
   ```bash
   python build.py
   ```

2. **Run the executable:**
   ```bash
   Shakshuka.exe
   ```

## Project Structure

```
Shakshuka/
├── main.py               # Main entry point (imports from src/)
├── src/
│   └── app.py            # Main Flask application
├── data_manager.py        # Encrypted data storage
├── autostart.py          # Windows autostart functionality
├── build.py              # Build script for executable
├── requirements.txt      # Python dependencies
├── Shakshuka.spec        # PyInstaller configuration
├── templates/
│   └── index.html        # Main HTML template
├── static/
│   ├── css/
│   │   └── style.css     # Modern CSS styles
│   ├── js/
│   │   └── app.js        # Frontend JavaScript
│   └── images/           # Static images
└── data/                 # Encrypted data storage (created automatically)
```

## Technology Stack

- **Backend:** Python Flask
- **Frontend:** HTML5, CSS3, JavaScript (ES6+)
- **Encryption:** Python Cryptography library
- **Build Tool:** PyInstaller
- **UI Framework:** Custom CSS with modern design patterns

## Key Features Explained

### Encrypted Storage
All task data is encrypted using Fernet symmetric encryption before being stored locally. The encryption key is derived from a password using PBKDF2.

### Modern UI Design
The interface is inspired by meditation and wellness apps, featuring:
- Soft gradient backgrounds
- Glass-morphism effects
- Rounded corners and smooth shadows
- Warm color palette (pinks, corals, whites)
- Intuitive navigation

### Drag-and-Drop Planner
The daily planner allows you to:
- Drag tasks from the task pool to specific time slots
- Visualize your daily schedule
- Navigate between dates
- See task durations and categories

### Auto-Save & Autostart
- Tasks are automatically saved every 30 seconds (configurable)
- Optional Windows autostart for seamless experience
- Data persists through application updates

## Configuration

### Settings Available:
- **Autostart:** Start with Windows
- **Auto-save interval:** 15 seconds to 5 minutes
- **Theme:** Light/Dark/Auto
- **Data export/import**

### Data Storage:
- Tasks are stored in encrypted files in the `data/` directory
- Settings are stored separately in encrypted format
- All data survives application updates

## Browser Compatibility

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## System Requirements

- **OS:** Windows 10/11 (primary), macOS/Linux (with limitations)
- **Python:** 3.8+ (if running from source)
- **RAM:** 512MB minimum
- **Storage:** 50MB for application + data

## Development

### Running in Development Mode:
```bash
python main.py
```
The app will run with debug mode enabled and auto-reload on changes.

### Building for Distribution:
```bash
python build.py
```
This creates a standalone executable that can be distributed without Python installation.

## Troubleshooting

### Common Issues:

1. **Port 5000 already in use:**
   - Change the port in `app.py` (line with `app.run()`)
   - Or kill the process using port 5000

2. **Permission errors on Windows:**
   - Run as Administrator
   - Check Windows Defender settings

3. **Build fails:**
   - Ensure all dependencies are installed
   - Check Python version compatibility
   - Verify PyInstaller installation

## License

This project is open source and available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

---

**Shakshuka** - Making task management beautiful and secure. ✨

