import json
import glob
import os
from collections import defaultdict

def print_statistics(data):
    """Print detailed statistics about the artist data"""
    total_artists = len(data)
    total_occurrences = sum(sum(name["number"] for name in entry["name"]) for entry in data if entry["name"])
    
    print(f"\n=== Statistics ===")
    print(f"Unique artist IDs: {total_artists}")
    print(f"Total artist occurrences: {total_occurrences}")
    
    # Find artists with multiple name variations
    artists_with_multiple_names = [entry for entry in data if len(entry.get("name", [])) > 1]
    print(f"Artists with multiple name variations: {len(artists_with_multiple_names)}")
    
    # Top 10 artists by occurrence
    print(f"\nTop 10 artists by occurrence:")
    count = 0
    for i, entry in enumerate(data):
        if count >= 10:
            break
            
        # Safely get the name list
        name_list = entry.get("name", [])
        if not name_list:  # Skip entries with no names
            continue
            
        total = sum(name.get("number", 0) for name in name_list)
        primary_name = name_list[0].get("text", "Unknown") if name_list else "Unknown"
        name_count = len(name_list)
        
        # Safely handle ID
        artist_id = entry.get("id", "Unknown")
        id_preview = artist_id[:10] if artist_id and len(artist_id) > 10 else artist_id
        
        print(f"{count+1}. {primary_name[:30]}{'...' if len(primary_name) > 30 else ''} (ID: {id_preview}...) - {total} occurrences, {name_count} name variation(s)")
        count += 1
    
    # If we didn't get 10 items
    if count < 10:
        print(f"(Only found {count} artists with valid data)")

# Also update the main extraction function to handle missing data more safely
def extract_and_combine_artists():
    # Find all files ending with _listmetadata.json in ./list/ directory
    file_pattern = "./list/*_listmetadata.json"
    json_files = glob.glob(file_pattern)
    
    # Dictionary to store artist data grouped by ID
    # Structure: {id: {"names": {name: count}, "total_count": total}}
    artists_by_id = defaultdict(lambda: {"names": defaultdict(int), "total_count": 0})
    
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
                # Check if data is an array
                if isinstance(data, list):
                    for item in data:
                        # Process album-level artists
                        if item and 'albumData' in item and item['albumData'] and 'artists' in item['albumData']:
                            artists = item['albumData']['artists']
                            
                            # Process each artist in the album-level list
                            if isinstance(artists, list):
                                for artist in artists:
                                    if artist and 'id' in artist and 'name' in artist and artist['id'] and artist['name']:
                                        artist_id = artist['id']
                                        artist_name = artist['name']
                                        
                                        # Increment the count for this name under this ID
                                        artists_by_id[artist_id]["names"][artist_name] += 1
                                        artists_by_id[artist_id]["total_count"] += 1
                        
                        # Process track-level artists
                        if (item and 'albumData' in item and item['albumData'] and 
                            'tracks' in item['albumData'] and item['albumData']['tracks']):
                            tracks = item['albumData']['tracks']
                            
                            # Check if tracks is an array
                            if isinstance(tracks, list):
                                for track in tracks:
                                    # Check if track has artists
                                    if track and 'artists' in track and track['artists']:
                                        track_artists = track['artists']
                                        
                                        # Process each artist in the track
                                        if isinstance(track_artists, list):
                                            for artist in track_artists:
                                                if artist and 'id' in artist and 'name' in artist and artist['id'] and artist['name']:
                                                    artist_id = artist['id']
                                                    artist_name = artist['name']
                                                    
                                                    # Increment the count for this name under this ID
                                                    artists_by_id[artist_id]["names"][artist_name] += 1
                                                    artists_by_id[artist_id]["total_count"] += 1
        
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error processing file {file_path}: {e}")
        except Exception as e:
            print(f"Unexpected error with file {file_path}: {e}")
    
    # Transform the data into the desired output format
    combined_data = []
    
    for artist_id, data in artists_by_id.items():
        # Skip if no valid names
        if not data["names"]:
            continue
            
        # Convert the names dictionary to the required format
        names_list = [
            {"text": name, "number": count} 
            for name, count in data["names"].items()
        ]
        
        # Sort names list by count in descending order
        names_list.sort(key=lambda x: x["number"], reverse=True)
        
        # Create the artist entry
        artist_entry = {
            "id": artist_id,
            "name": names_list
        }
        
        combined_data.append(artist_entry)
    
    # Sort by total count in descending order
    combined_data.sort(key=lambda x: sum(name["number"] for name in x["name"]), reverse=True)
    
    return combined_data

def save_combined_data(data, output_file="grouped_artists.json"):
    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=3, ensure_ascii=False)
        print(f"Successfully saved data for {len(data)} unique artist IDs to {output_file}")
    except IOError as e:
        print(f"Error saving output file: {e}")

# Main execution
if __name__ == "__main__":
    result = extract_and_combine_artists()
    
    # Print statistics
    print_statistics(result)
    
    # Print sample of results
    if result:
        print("\n=== Sample (first 3 items) ===")
        # Print only first few names for each sample to keep output readable
        sample = []
        for entry in result[:3]:
            entry_sample = entry.copy()
            # Limit to first 5 names for sample display
            entry_sample["name"] = entry["name"][:5]
            if len(entry["name"]) > 5:
                entry_sample["name"].append({"text": "... and more", "number": len(entry["name"]) - 5})
            sample.append(entry_sample)
        print(json.dumps(sample, indent=3, ensure_ascii=False))
    
    # Save to file
    save_combined_data(result)
    
    # Optional: Save with more readable filename
    # save_combined_data(result, "artist_name_variations.json")