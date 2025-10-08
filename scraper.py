from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
import time
import re
import pandas as pd
service = Service(ChromeDriverManager().install())
service = Service(ChromeDriverManager().install())

def clean_ordinal(date_str):
    return re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)

def get_numeric_xg(tags):
    for tag in tags:
        text = tag.text.strip()
        try:
            return float(text)
        except ValueError:
            continue
    return None

def scroll_to_load_all_fixtures(driver):
    SCROLL_PAUSE = 2
    MAX_SCROLL_ATTEMPTS = 10
    last_fixture_count = 0

    for _ in range(MAX_SCROLL_ATTEMPTS):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        fixtures = driver.find_elements(By.CLASS_NAME, "fixture")
        new_fixture_count = len(fixtures)

        if new_fixture_count == last_fixture_count:
            break
        last_fixture_count = new_fixture_count

    print(f"Toplam yüklenen maç sayısı: {last_fixture_count}")

# 🌐 Web scraping başlat
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get("https://oddalerts.com/xg")
time.sleep(6)
scroll_to_load_all_fixtures(driver)

html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# 🔍 Maçları bul
all_blocks = soup.select('.fixture.heading, .fixture')
matches = []
current_date = None

for block in all_blocks:
    class_list = block.get("class", [])

    if "heading" in class_list:
        date_tag = block.select_one('.status-text')
        if date_tag:
            raw_date = date_tag.text.strip()
            cleaned_date = clean_ordinal(raw_date)
            try:
                current_date = datetime.strptime(cleaned_date + " 2025", "%A, %d %B %Y")
            except Exception:
                current_date = cleaned_date
    else:
        try:
            teams = block.select('.team')
            if len(teams) < 2:
                continue

            home_name = teams[0].select_one('.name').text.strip()
            away_name = teams[1].select_one('.name').text.strip()

            home_xg = get_numeric_xg(teams[0].select('.xg'))
            away_xg = get_numeric_xg(teams[1].select('.xg'))

            if home_xg is None or away_xg is None:
                continue

            matches.append({
                "Date": current_date,
                "HomeTeam": home_name,
                "AwayTeam": away_name,
                "HxG": home_xg,
                "AxG": away_xg,
            })
        except Exception as e:
            print("Hata:", e)
            continue

driver.quit()

# 🔄 Mevcut CSV dosyasını oku (varsa)
try:
    existing_df = pd.read_csv("future_xg_matches.csv")
    existing_df["Date"] = pd.to_datetime(existing_df["Date"]).dt.date
except FileNotFoundError:
    existing_df = pd.DataFrame(columns=["Date", "HomeTeam", "AwayTeam", "HxG", "AxG"])

# 🆕 Yeni veriyi DataFrame'e dönüştür
df_new = pd.DataFrame(matches)
df_new["Date"] = pd.to_datetime(df_new["Date"]).dt.date

# 🔁 Birleştir ve tekrar eden maçları kaldır
combined_df = pd.concat([existing_df, df_new])
combined_df = combined_df.drop_duplicates(subset=["Date", "HomeTeam", "AwayTeam"], keep="last")
combined_df = combined_df.sort_values(by="Date").reset_index(drop=True)

# 🧮 xG farkı hesapla
combined_df["xG_diff"] = combined_df["HxG"] - combined_df["AxG"]

# 🔁 Takım adlarını normalize et
combined_df["HomeTeam"] = combined_df["HomeTeam"].str.strip()
combined_df["AwayTeam"] = combined_df["AwayTeam"].str.strip()

# 💬 team_name_map buraya eklendi (sadece örnek birkaç satır gösteriliyor)
team_name_map = {
     # Premier League (E0)
    "AFC Bournemouth":"Bournemouth",
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "Brentford FC": "Brentford",
    "Brighton & Hove Albion FC": "Brighton",
    "Burnley FC": "Burnley",
    "Chelsea FC": "Chelsea",
    "Crystal Palace FC": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Liverpool FC": "Liverpool",
    "Luton Town FC": "Luton",
    "Manchester City FC": "Man City",
    "Manchester United FC": "Man United",
    "Newcastle United FC": "Newcastle",
    "Nottingham Forest FC": "Nottm Forest",
    "Sheffield United FC": "Sheffield United",
    "Tottenham Hotspur FC": "Tottenham",
    "West Ham United FC": "West Ham",
    "Wolverhampton Wanderers FC": "Wolves",
    "Southampton FC":"Southampton",
    "Ipswich Town FC":"Ipswich",
    "Leicester City FC":"Leicester",


    # La Liga (SP1)
    "Real Madrid CF":"Real Madrid",
    "FC Barcelona":"Barcelona",
    "Espanyol": "Espanol",
    "Girona FC": "Girona",
    "RC Celta de Vigo": "Celta",
    "Real Betis Balompié": "Betis",
    "Valencia CF":"Valencia",
    "Getafe CF"	:"Getafe",
    "Sevilla FC":"Sevilla",
    "Villarreal CF":"Villarreal",
    "UD Las Palmas":"Las Palmas",
    "Club Atlético de Madrid":"Ath Madrid",
    "RCD Mallorca":"Mallorca",
    "Real Valladolid CF":"Valladolid",
    "Rayo Vallecano de Madrid":"Vallecano",
    "Real Sociedad de Fútbol":"Sociedad",
    'RCD Espanyol de Barcelona':'Espanol',
    "CD Leganés":"Leganes",
    "Athletic Club":"Ath Bilbao",
    

    # Serie A (I1)
    "AC Milan": "Milan",
    "Inter Milan": "Inter",
    "FC Internazionale Milano": "Inter",
    "SSC Napoli": "Napoli",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "Juventus FC": "Juventus",
    "Atalanta BC": "Atalanta",
    "Torino FC": "Torino",
    "Fiorentina": "Fiorentina",
    "ACF Fiorentina": "Fiorentina",
    "Udinese Calcio": "Udinese",
    "Bologna FC 1909": "Bologna",
    "Hellas Verona FC": "Verona",
    "US Lecce": "Lecce",
    "Empoli FC": "Empoli",
    "Genoa CFC": "Genoa",
    "Cagliari Calcio": "Cagliari",
    "Como 1907": "Como",
    "AC Monza": "Monza",
    "Parma Calcio 1913": "Parma",
    "Venezia FC":"Venezia",
    "Deportivo Alavés":"Alaves",
    "CA Osasuna":"Osasuna",

    # Ligue 1 (F1)
    "Paris Saint-Germain FC": "Paris SG",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "AS Monaco FC": "Monaco",
    "Lille OSC": "Lille",
    "OGC Nice": "Nice",
    "Stade Rennais FC 1901": "Rennes",
    "RC Strasbourg Alsace": "Strasbourg",
    "FC Nantes": "Nantes",
    "Stade Brestois 29": "Brest",
    "Toulouse FC": "Toulouse",
    "Montpellier HSC": "Montpellier",
    "Le Havre AC": "Le Havre",
    "Stade de Reims": "Reims",
    "Clermont Foot 63": "Clermont",
    "Metz": "Metz",
    "RC Lens": "Lens",
    "Angers SCO": "Angers",
    "AJ Auxerre": "Auxerre",
    "AS Saint-Étienne": "St Etienne",
    "Racing Club de Lens":"Lens",

    #Bundesliga
    "Bayer 04 Leverkusen":"Leverkusen",
    "FC Augsburg":"Augsburg",
    "FC St. Pauli 1910":"St Pauli",
    "SV Werder Bremen":"Werder Bremen",
    "1. FC Heidenheim 1846":"Heidenheim",
    "1 FC Heidenheim 1846":"Heidenheim",
    "TSG 1899 Hoffenheim": "Hoffenheim",
    "FC St Pauli": "St Pauli",
    "1 FC Heidenheim": "Heidenheim",
    "VfL Bochum 1848": "Bochum",
    'Borussia Mönchengladbach': "MGladbach",
    'Borussia Dortmund':"Dortmund",
    "Bayer Leverkusen":"Leverkusen",
    'Eintracht Frankfurt':"Ein Frankfurt",
     'VfB Stuttgart':"Stuttgart",
    "Borussia Monchengladbach": "MGladbach",
    "Bayer Leverkusen": "Leverkusen", 
    "1. FSV Mainz 05": "Mainz",
    "Mainz 05": "Mainz",
    "SC Freiburg": "Freiburg",
    "VfL Wolfsburg": "Wolfsburg",
    "VfB Stuttgart": "Stuttgart", 
    "FC Bayern München":"Bayern Munich",
    "1. FC Union Berlin":"Union Berlin",
    "1 FC Union Berlin":"Union Berlin",
    "TSG Hoffenheim": "Hoffenheim",
    "FC St Pauli": "St Pauli",
    "1 FC Heidenheim": "Heidenheim",
    "VfL Bochum": "Bochum",
    'Borussia Mönchengladbach': "MGladbach",
    'Borussia Dortmund':"Dortmund",
    "Bayer Leverkusen":"Leverkusen",
    'Eintracht Frankfurt':"Ein Frankfurt",
     'VfB Stuttgart':"Stuttgart",
    "Borussia Monchengladbach": "MGladbach",
    "Bayer Leverkusen": "Leverkusen", 
    "FSV Mainz 05": "Mainz 05",
    "SC Freiburg": "Freiburg",
    "VfL Wolfsburg": "Wolfsburg",
    "VfB Stuttgart": "Stuttgart",
    "1. FC Heidenheim":"Heidenheim",
    "Mainz 05":"Mainz",
    "FC St. Pauli":"St Pauli",
    "Bayer 04 Leverkusen":"Leverkusen",
    "FC Augsburg":"Augsburg",
    "FC St. Pauli 1910":"St Pauli",
    

    # Premier League
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Brighton and Hove Albion": "Brighton",
    "Brighton & Hove Albion": "Brighton",

    "Tottenham Hotspur": "Tottenham",
    "West Ham United": "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    "Leicester City": "Leicester",
    "Nottingham Forest": "Nottm Forest",
    "Newcastle United": "Newcastle",
    "Sevilla FC":"Sevilla",
    "Ipswich Town":"Ipswich",

    # La Liga
    "Atlético Madrid": "Ath Madrid",
    "Athletic Bilbao": "Ath Bilbao",
    "RC Lens": "Lens",
    "Rayo Vallecano": "Vallecano",
    "Real Sociedad": "Sociedad",
    "Real Betis": "Betis",
    "CA Osasuna": "Osasuna",
    "Leganés": "Leganes",
    "Celta Vigo": "Celta",
    "Espanyol": "Espanol",
    "Alavés":"Alaves",

    # Serie A
    "AC Milan": "Milan",
    "Inter Milan": "Inter",
    "AS Roma": "Roma",
    "Atalanta BC": "Atalanta",
    "Hellas Verona": "Verona",
    "AS Monaco": "Monaco",  # Monaco aslında Ligue 1 ama API'de İtalya olabilir
    "Paris Saint Germain": "Paris SG",

    # Ligue 1
    "Saint Etienne": "St Etienne",
    "Stade de Reims": "Reims",
    "Racing Club de Lens":"Lens",
}

combined_df["HomeTeam"] = combined_df["HomeTeam"].replace(team_name_map)
combined_df["AwayTeam"] = combined_df["AwayTeam"].replace(team_name_map)

# 🔢 Ondalıklı sayıları 2 basamakla sınırla
combined_df[["HxG", "AxG", "xG_diff"]] = combined_df[["HxG", "AxG", "xG_diff"]].round(2)
combined_df = combined_df.drop_duplicates(subset=["Date", "HomeTeam", "AwayTeam"], keep="last")

# 💾 CSV dosyasına yaz
combined_df.to_csv("future_xg_matches.csv", index=False)
print("✅ future_xg_matches.csv güncellendi.")
print(combined_df.tail())