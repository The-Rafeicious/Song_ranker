import requests
import json


def test_apple_query(title, artist, album=""):
    query = f"{title} {artist} {album}".strip().replace(" ", "+")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=5&explicit=Yes"

    try:
        response = requests.get(url, timeout=5).json()
        print(f"\n--- API Results for: '{title}' by {artist} [{album}] ---")
        print(f"Total Found: {response.get('resultCount', 0)}\n")

        if response.get('resultCount', 0) > 0:
            for i, track in enumerate(response['results'][:5], 1):
                name = track.get('trackName', 'Unknown')
                collection = track.get('collectionName', 'Unknown')
                explicit = track.get('trackExplicitness', 'not specified')

                print(f"Result #{i}:")
                print(f"  Track:  {name}")
                print(f"  Album:  {collection}")
                print(f"  Tag:    {explicit.upper()}")
                print("-" * 50)
        else:
            print("No results found.")
    except Exception as e:
        print(f"Error: {e}")


# You can change these variables to test any song
if __name__ == "__main__":
    test_apple_query("DON'T YOU SEE ME TRYING?", "Erin LeCount")