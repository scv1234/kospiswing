import sys
import os
sys.path.append(os.getcwd())
from utils.data_fetcher import get_ticker_mapping

print("Testing get_ticker_mapping...")
df = get_ticker_mapping()
print(f"Result Shape: {df.shape}")
print(f"Columns: {df.columns}")
if not df.empty:
    print(df.head())
else:
    print("DataFrame is empty!")
