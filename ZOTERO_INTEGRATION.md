# Zotero Integration for AI Ethical Decision-Making Simulator

This document provides instructions for integrating the Zotero MCP server with the AI Ethical Decision-Making Simulator.

## Overview

The Zotero integration allows you to:

1. Search for academic references related to ethical scenarios
2. Retrieve citations in various formats (APA, MLA, Chicago)
3. Add new references to your Zotero library
4. Generate bibliographies for research and case studies

## Prerequisites

- A Zotero account (https://www.zotero.org/user/register)
- Zotero API key (https://www.zotero.org/settings/keys/new)
- Your Zotero user ID (found in your profile URL: https://www.zotero.org/[user_id])

## Installation

1. Clone the Zotero MCP server repository:
   ```bash
   git clone https://github.com/your-username/zotero-mcp-server.git
   cd zotero-mcp-server
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your Zotero API credentials:
   - Copy `.env.example` to `.env`
   - Edit `.env` to add your Zotero API key and user ID

## Configuration

1. In the AI Ethical Decision-Making Simulator project:
   - Copy `.env.example` to `.env` if you haven't already
   - Add your Zotero API credentials to the `.env` file:
     ```
     ZOTERO_API_KEY=your-zotero-api-key-here
     ZOTERO_USER_ID=your-zotero-user-id-here
     ```

2. The MCP client has been updated to support both the existing ethical-dm server and the new Zotero server. No additional configuration is needed.

## Usage

### Accessing References for a World

1. Navigate to a world detail page
2. Click the "World References" button in the top-right corner
3. The system will automatically suggest references based on the world content
4. You can also search for specific references using the search box

### Accessing References for a Scenario

1. Navigate to a scenario detail page
2. Click the "References" button in the top-right corner
3. The system will automatically suggest references based on the scenario content
4. You can also search for specific references using the search box

### Adding References

1. On the references page, click the "Add Reference" button
2. Fill in the reference details (title, authors, journal, etc.)
3. Click "Save Reference" to add it to your Zotero library

### Getting Citations

1. On the references page, click the "Get Citation" button for a reference
2. Select the citation style (APA, MLA, Chicago)
3. Copy the citation for use in your research or documentation

## Troubleshooting

### API Key Issues

If you encounter errors related to the Zotero API key:

1. Verify that your API key is correct in the `.env` file
2. Ensure your API key has the necessary permissions (read/write)
3. Check that your user ID is correct

### Server Connection Issues

If the Zotero MCP server fails to start:

1. Check that the server path is correct in the MCP client
2. Verify that all dependencies are installed
3. Check the server logs for error messages

## Advanced Configuration

### Using a Group Library

If you want to use a Zotero group library instead of your personal library:

1. Find your group ID in the group URL: https://www.zotero.org/groups/[group_id]
2. Add the group ID to your `.env` file:
   ```
   ZOTERO_GROUP_ID=your-group-id-here
   ```
3. Uncomment the `ZOTERO_GROUP_ID` line in the `.env` file

### Custom Citation Styles

The default citation styles are APA, MLA, and Chicago. If you need additional styles:

1. Find the style identifier on the Zotero Style Repository (https://www.zotero.org/styles)
2. Add the style to the citation style buttons in the `scenario_references.html` template

## Contributing

If you'd like to contribute to the Zotero MCP server:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT
