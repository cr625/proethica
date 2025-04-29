const puppeteer = require('puppeteer');

(async () => {
  console.log('Launching browser...');
  try {
    const browser = await puppeteer.launch({
      executablePath: '/usr/bin/chromium-browser',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
      headless: 'new'
    });
    
    console.log('Browser launched successfully!');
    
    const page = await browser.newPage();
    console.log('Navigating to example.com...');
    await page.goto('https://example.com');
    console.log('Page title:', await page.title());
    
    // Take a screenshot
    await page.screenshot({ path: 'example_screenshot.png' });
    console.log('Screenshot saved as example_screenshot.png');
    
    await browser.close();
    console.log('Browser closed.');
  } catch (error) {
    console.error('Error occurred:', error);
    console.log('\nTROUBLESHOOTING TIPS:');
    console.log('1. Make sure all dependencies are installed (see docs/puppeteer_wsl_setup.md)');
    console.log('2. Check if the chromium-browser path is correct');
    console.log('3. Try setting the PUPPETEER_EXECUTABLE_PATH environment variable');
  }
})();
