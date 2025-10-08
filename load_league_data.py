import pandas as pd
import os

def load_historical_league_data(data_dir="Data"):
    league_files = {
        "D1": "D1_matches.csv",    # Bundesliga
        "E0": "E0_matches.csv",    # Premier League
        "SP1": "SP1_matches.csv",  # La Liga
        "I1": "I1_matches.csv",    # Serie A
        "F1": "F1_matches.csv",    # Ligue 1
        "T1": "T1_matches.csv",    # Süper Lig
    }

    leagues = {}

    for code, filename in league_files.items():
        path = os.path.join(data_dir, filename)
        try:
            df = pd.read_csv(path)
            if "Date" not in df.columns:
                print(f"⚠️ {code}: 'Date' sütunu bulunamadı, geçildi.")
                continue
            df["Date"] = pd.to_datetime(df["Date"])
            leagues[code] = df
        except FileNotFoundError:
            print(f"❌ {code}: Dosya bulunamadı → {filename}")
        except Exception as e:
            print(f"❌ {code}: Hata oluştu → {e}")

    return leagues
