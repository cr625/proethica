#!/usr/bin/env python3
import requests

def test_url():
    url = 'http://localhost:3333/worlds/1/guidelines/190'
    print(f"Testing URL: {url}")
    try:
        response = requests.get(url, timeout=5)
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("URL is accessible")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_url()
