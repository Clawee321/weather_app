import tkinter as tk
from tkinter import messagebox
import requests
from io import BytesIO
from PIL import Image, ImageTk

# 🔑 Wpisz swój klucz API tutaj
API_KEY = "9f5d80b974ba325f52a205863ee448c6"  
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# 🌤️ Funkcja pobierająca dane pogodowe
def get_weather():
    city = city_entry.get()
    if not city:
        messagebox.showwarning("Błąd", "Wpisz nazwę miasta!")
        return
    
    params = {
        "q": city,
        "appid": API_KEY,
        "units": "metric",
        "lang": "pl"
    }
    try:
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        if data.get("cod") != 200:
            messagebox.showerror("Błąd", f"Nie znaleziono miasta: {city}")
            return
        
        temp = data["main"]["temp"]
        desc = data["weather"][0]["description"].capitalize()
        icon_code = data["weather"][0]["icon"]
        
        result_label.config(text=f"{city}\n{temp}°C\n{desc}")
        
        # Pobierz i pokaż ikonę pogody
        icon_url = f"http://openweathermap.org/img/wn/{icon_code}@2x.png"
        icon_response = requests.get(icon_url)
        icon_img = Image.open(BytesIO(icon_response.content))
        icon_photo = ImageTk.PhotoImage(icon_img)
        icon_label.config(image=icon_photo)
        icon_label.image = icon_photo
        
    except Exception as e:
        messagebox.showerror("Błąd", f"Wystąpił problem:\n{e}")

# 🪟 Tworzenie GUI
root = tk.Tk()
root.title("Aplikacja pogodowa")
root.geometry("300x400")
root.resizable(False, False)

title_label = tk.Label(root, text="Sprawdź pogodę", font=("Arial", 16, "bold"))
title_label.pack(pady=10)

city_entry = tk.Entry(root, font=("Arial", 12))
city_entry.pack(pady=5)

search_button = tk.Button(root, text="Pobierz pogodę", command=get_weather)
search_button.pack(pady=5)

icon_label = tk.Label(root)
icon_label.pack()

result_label = tk.Label(root, font=("Arial", 14))
result_label.pack(pady=10)

root.mainloop()
