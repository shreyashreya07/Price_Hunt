# PriceHunt — README.md

## 📌 Project Title

# PriceHunt — Smart Price Comparison Web Application

---

## 📖 Introduction

PriceHunt is a Django-based web application that helps users compare product prices from multiple e-commerce platforms such as [Flipkart](https://www.flipkart.com?utm_source=chatgpt.com), [Amazon India](https://www.amazon.in?utm_source=chatgpt.com), [Snapdeal](https://www.snapdeal.com?utm_source=chatgpt.com), and [Meesho](https://www.meesho.com?utm_source=chatgpt.com).

The system uses web scraping techniques to collect real-time product details including:

* Product Name
* Product Price
* Product Image
* Product Link
* Platform Name

Users can search for products, compare prices, apply price filters, and identify the best available deal instantly.

---

# 🚀 Features

* 🔍 Product Search
* 💰 Price Comparison
* 📊 Lowest Price Highlight
* 🛒 Multiple Platform Support
* 🖼 Product Images
* 🎯 Price Range Filter
* 📧 Email Price Alert
* 🕘 Search History
* 📱 Responsive UI Design

---

# 🛠 Technologies Used

## Frontend

* HTML5
* CSS3
* Bootstrap 5
* JavaScript

## Backend

* Python
* Django

## Database

* SQLite / MySQL

## Libraries

* BeautifulSoup
* Requests

---

# ⚙️ Platforms Supported

* [Flipkart](https://www.flipkart.com?utm_source=chatgpt.com)
* [Amazon India](https://www.amazon.in?utm_source=chatgpt.com)
* [Snapdeal](https://www.snapdeal.com?utm_source=chatgpt.com)
* [Meesho](https://www.meesho.com?utm_source=chatgpt.com)

---

# 📂 Project Structure

```bash
PriceHunt/
│
├── products/
│   ├── templates/
│   ├── static/
│   ├── scraper.py
│   ├── views.py
│   ├── models.py
│   ├── urls.py
│
├── manage.py
├── db.sqlite3
└── requirements.txt
```

---

# 🔄 Working Process

1. User enters a product name in the search bar.
2. Django receives the search query through `views.py`.
3. The query is sent to `search_products(query)`.
4. Scrapers collect product data from multiple shopping websites.
5. Prices are cleaned and converted into integer format.
6. Results are filtered and sorted by lowest price.
7. Top product deals are displayed to the user.

---

# 📌 Main Modules

## 1. Product Search Module

Allows users to search for products.

## 2. Price Comparison Module

Compares prices across multiple platforms.

## 3. Filter Module

Filters products based on minimum and maximum price.

## 4. Price Alert Module

Sends email notifications for price updates.

## 5. Search History Module

Stores previous user searches.

---

# 📸 Output Screens

* Home Page
* Search Results Page
* Product Comparison Cards
* Price Filter Section
* Best Deal Highlight

---

# 🎯 Objectives

* To compare product prices from different platforms.
* To help users save money and time.
* To provide real-time product information.
* To build a responsive and user-friendly system.

---

# ✅ Conclusion

PriceHunt simplifies online shopping by collecting and comparing product prices from multiple e-commerce websites in one place.
The system reduces manual searching effort and helps users quickly find the best deals.
Using Django and web scraping techniques, the project provides real-time product comparison efficiently.
The application offers a clean user interface, price filtering, and alert features for better user experience.
Overall, PriceHunt is a smart and useful solution for online price comparison and deal tracking.
