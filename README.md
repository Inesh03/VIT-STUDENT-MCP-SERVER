# 🎓 VIT Student MCP Server

<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=22&duration=3000&pause=1000&color=3B82F6&center=true&vCenter=true&width=800&lines=Your+Personal+Academic+Assistant;Auto-solving+Captchas+with+AI...;Syncing+Marks,+Attendance,+and+Exams...;Seamlessly+Integrated+with+Claude!" alt="Typing SVG" />
</p>

<p align="center">
  <a href="https://pypi.org/project/vit-student-mcp/"><img src="https://badge.fury.io/py/vit-student-mcp.svg" alt="PyPI version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
</p>

**Turn Claude AI into your personal academic assistant.**

The **VIT Student MCP Server** seamlessly bridges the gap between your university's portal (VTOP) and your local Claude Desktop app using the powerful Model Context Protocol (MCP). It silently scrapes your academic profile—Marks, Attendance, Timetable, Exams, and Assignments—and equips Claude with real-time access to your academic life.

Ask Claude things like:
- *"What's my schedule tomorrow?"*
- *"Am I debarred in any subject?"*
- *"How many more classes do I need to attend in Cloud Computing to hit 75%?"*
- *"Did I get the marks for my recent CAT-1 exam?"*

---

## ✨ Features

- **🚀 1-Click Installation:** Now available on PyPI! Install globally with a single command.
- **🤖 Auto-Captcha Bypass:** Uses a lightweight local neural network (`ddddocr`) to instantly solve VTOP login captchas. No manual typing required.
- **🛡️ Secure & Local:** Your VTOP password is **never saved**. All scraped data is stored securely in a local SQLite file (`~/.vit_student_mcp/vit_student.db`) on your own hard drive.
- **⚡ Lightning Fast:** By caching your data locally, Claude can answer your academic questions instantly without waiting for slow website loads.

---

## 🛠️ Installation

### 1. Install the Package
Open your terminal and install the package globally using `pip`:
```bash
pip install vit-student-mcp
```
*(If you use Conda or virtual environments, make sure your environment is activated first).*

### 2. Install Playwright Browsers
The scraper requires a hidden Chromium browser to navigate VTOP:
```bash
playwright install chromium
```

---

## 🔄 Syncing Your Data

Before Claude can answer questions, you need to securely pull your data from VTOP into your local database. 

Simply run this command anywhere in your terminal:
```bash
vit-mcp-sync
```

1. Enter your **Registration Number** and **Password**.
2. Grab a coffee ☕. The script will open a hidden browser, solve the Captcha, bypass the login, and securely download your entire academic profile!

*(Note: You should run this command whenever you want to update Claude with your latest marks or attendance).*

---

## 🧠 Connecting to Claude Desktop

Now, let's give Claude the keys to your academic data.

1. Open your Claude Desktop Configuration File:
   - **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. Add the following configuration. Replace `/path/to/your/python` with the absolute path to the Python environment where you installed the package.

```json
{
  "mcpServers": {
    "vit-academic-assistant": {
      "command": "/path/to/your/python",
      "args": [
        "-m",
        "vit_student_mcp.server"
      ]
    }
  }
}
```
*(Tip: To find your python path, run `which python` or `where python` in your terminal).*

3. **Restart Claude Desktop**. You should now see the "plug" 🔌 icon in the chat bar, meaning your VIT Assistant is fully operational and ready to help!

---

## 📝 Disclaimer

This tool is entirely local and open-source. It simulates a browser session to access your own data on your behalf. Your credentials are used strictly for the active session and are **never logged, tracked, or uploaded** to any third-party server.
