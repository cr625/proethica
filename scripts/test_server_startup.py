#!/usr/bin/env python3
"""
Script to test if the server can start properly after syntax fixes.
"""
import os
import sys
import subprocess
import time

def test_server_startup():
    """
    Start the server and check if it runs without syntax errors.
    """
    print("Starting ProEthica server...")
    
    # Start the server using start_proethica.sh in a separate process
    server_process = subprocess.Popen(
        ["./start_proethica.sh"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Wait for a bit to see if the server starts
    time.sleep(5)
    
    # Check if the server is running
    if server_process.poll() is None:
        print("Server appears to be running!")
        
        # Try to access the server
        try:
            import requests
            print("Testing server connection...")
            response = requests.get("http://localhost:3333", timeout=5)
            if response.status_code == 200:
                print(f"Server responded with status code {response.status_code}")
            else:
                print(f"Server responded with status code {response.status_code}")
                
            print("Testing ontology editor connection...")
            editor_response = requests.get("http://localhost:3333/ontology-editor", timeout=5)
            if editor_response.status_code == 200:
                print(f"Ontology editor responded with status code {editor_response.status_code}")
            else:
                print(f"Ontology editor responded with status code {editor_response.status_code}")
        
        except Exception as e:
            print(f"Error connecting to server: {str(e)}")
        
        # Terminate the server
        print("Terminating test server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
            print("Server terminated successfully")
        except subprocess.TimeoutExpired:
            print("Server did not terminate gracefully, killing process...")
            server_process.kill()
        
        return True
    else:
        # Server failed to start, get output
        output, _ = server_process.communicate()
        print("Server failed to start. Output:")
        print(output)
        return False

if __name__ == "__main__":
    if test_server_startup():
        print("\nServer startup test succeeded!")
    else:
        print("\nServer startup test failed. Check the output for errors.")
