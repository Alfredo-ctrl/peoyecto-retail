import json

# Check detection data
d = json.load(open("3d-demo/detection_data.json", encoding="utf-8"))
print("=== DETECTION RESULTS ===")
for k, v in d.items():
    print(f"  {k}: {v['total_detections']} detected, catalog={v['catalog_total']}, avgConf={v['avg_confidence']}")

# Check inventory
inv = json.load(open("3d-demo/real_inventory.json", encoding="utf-8"))
print(f"\n=== INVENTORY ({len(inv['inventory'])} items) ===")
for item in inv["inventory"]:
    print(f"  [{item['section']}] {item['name']}: {item['qty']} units (conf: {item['avgConfidence']})")
