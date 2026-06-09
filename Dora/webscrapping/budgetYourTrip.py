# récuperer le code source de la page
from bs4 import BeautifulSoup as bs
import pandas as pd
import requests
# requête HTTP au site
res = requests.get("https://www.budgetyourtrip.com/france")

#print(res)
#print(res.content)

soup =  bs(res.content, 'html.parser')

#print(soup.prettify())

print(soup.find('div', class_= 'textcontent').find_all('li'))

""" 
cards_label = soup.find('li', class_= 'cost-tile cost-tile-main cost-tile-main-small cost-tile-two-values').find('div', class_="cost-tile-label")
cards_cost_dollars = soup.find('li', class_= 'cost-tile cost-tile-main cost-tile-main-small cost-tile-two-values').find('div', class_="cost-tile-value not-bottom")
cards_cost_euro = soup.find('li', class_= 'cost-tile cost-tile-main cost-tile-main-small cost-tile-two-values').find('div', class_="cost-tile-value-secondary")
print(cards_label)
print(cards_cost_dollars)
print(cards_cost_euro) """



data = []


sections = soup.find_all("li", class_="cost-tile cost-tile-main cost-tile-main-small cost-tile-two-values")

for section in sections:
    # Label + Description
    label = section.find("div", class_="cost-tile-label").get_text(strip=True)
    description = section.find("span", class_="cost-tile-label-description").get_text(strip=True)

    # Valeur en dollars
    dollar_value = section.find("div", class_="cost-tile-value").find("span", class_="curvalue").get_text(strip=True)
    dollar_symbol = section.find("div", class_="cost-tile-value").find("span", class_="symbol").get_text(strip=True)

    # Valeur en euros
    euro_value = section.find("div", class_="cost-tile-value-secondary").find("span", class_="curvalue2").get_text(strip=True)
    euro_symbol = section.find("div", class_="cost-tile-value-secondary").find("span", class_="symbol2").get_text(strip=True)


    data.append({
        "Label": label,
        "Description": description,
        "Dollar Symbol": dollar_symbol,
        "Dollar Value": dollar_value,
        "Euro Symbol": euro_symbol,
        "Euro Value": euro_value
    })


df = pd.DataFrame(data)
print(df)