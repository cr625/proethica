# Setting Up Puppeteer in WSL (Ubuntu 24.04 LTS)

Puppeteer is a Node.js library that provides a high-level API to control Chrome/Chromium over the DevTools Protocol. When running in WSL (Windows Subsystem for Linux), Puppeteer has specific requirements to run properly. This guide covers the necessary steps to get Puppeteer working in your WSL environment.

## Prerequisites

- WSL2 with Ubuntu 24.04 LTS
- Node.js (verified working with v18.19.1)

## Required Dependencies

Puppeteer requires several system libraries to function correctly. Install them using apt:

```bash
sudo apt update
sudo apt install -y \
    chromium-browser \
    libx11-xcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libxshmfence1 \
    libgles2
```

## Installing Puppeteer

### Option 1: Global Installation

```bash
npm install -g puppeteer
```

### Option 2: Project-specific Installation

```bash
npm install puppeteer
```

## WSL-Specific Configuration

### 1. Use --no-sandbox Mode

When running Puppeteer in WSL, you may need to use the `--no-sandbox` flag. This is generally safe in a development environment but should be avoided in production.

Example configuration:

```javascript
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium-browser',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  // Rest of your code
})();
```

### 2. Address Display Server Issues

WSL doesn't include a display server by default. You have a few options:

#### Option A: Use headless mode (recommended for most cases)

```javascript
const browser = await puppeteer.launch({
  headless: 'new',
  executablePath: '/usr/bin/chromium-browser',
  args: ['--no-sandbox', '--disable-setuid-sandbox']
});
```

#### Option B: Set up X server forwarding (if you need visual debugging)

1. Install an X server on Windows (like VcXsrv)
2. Export the DISPLAY environment variable in WSL:

```bash
export DISPLAY=$(grep nameserver /etc/resolv.conf | awk '{print $2}'):0
```

### 3. Environment Variables

Add these to your ~/.bashrc or ~/.zshrc file:

```bash
export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
```

This prevents Puppeteer from downloading its own Chromium and instead uses the system-installed version.

## Troubleshooting

### Error: Failed to launch the browser process!

This typically means missing dependencies. Try installing all the libraries listed above.

### Error: Chromium revision is not downloaded

Set the environment variables as described above to use the system Chromium.

### Error: No usable sandbox!

Add the `--no-sandbox` flag to the launch options as shown above.

### Browser appears to be offline

This may be due to networking issues in WSL. Try restarting your WSL instance:

```bash
wsl --shutdown
```

Then restart your terminal.

## Testing Your Setup

Create a simple test script:

```javascript
// test-puppeteer.js
const puppeteer = require('puppeteer');

(async () => {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium-browser',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    headless: 'new'
  });
  
  console.log('Browser launched successfully!');
  
  const page = await browser.newPage();
  await page.goto('https://example.com');
  console.log('Page title:', await page.title());
  
  await browser.close();
  console.log('Browser closed.');
})().catch(err => {
  console.error('Error occurred:', err);
});
```

Run it with:

```bash
node test-puppeteer.js
```

## Additional Resources

- [Puppeteer Troubleshooting Guide](https://pptr.dev/troubleshooting)
- [Running Puppeteer in Docker](https://pptr.dev/guides/docker)
- [WSL Documentation](https://learn.microsoft.com/en-us/windows/wsl/)

---

If you continue experiencing issues after following these steps, please check the Puppeteer GitHub issues or consider using a Docker container specifically configured for Puppeteer.
