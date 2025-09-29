# 🏠 Inmobil-IA-ria.com  

Inmobil-IA-ria is a **Machine Learning platform** designed as a practical case study for analyzing real estate data, building predictive models, and generating automated investment reports.  

> ⚠️ **Note**: The CSV datasets are not included in this repository. The scraping code is presented only as a **technical exercise** and not intended for production use now.  

---

## 📂 Project Structure  

### 🔹 `Idealista_indexes.ipynb`  
Collects the IDs of available listings from Idealista (indexing step).  

### 🔹 `Idealista_data.ipynb`  
Uses those IDs to access individual listings and retrieve property details (title, price, location, features, etc.).  

### 🔹 `Dataframe.ipynb`  
Transforms the collected raw information into a **structured DataFrame**, cleaning and engineering relevant features.  

### 🔹 `ML_models.ipynb`  
Trains **Machine Learning models** (e.g., Bagging, Gradient Boosting, SVR) using the processed dataset to predict property values and detect undervalued opportunities.  

### 🔹 `Clients.ipynb`  
Manages client profiles: each client specifies the property features of interest, so only the listings that match their preferences are sent to them.  

### 🔹 `Charts.ipynb`  
Generates visualizations and comparative charts (price distributions, €/m², property size, number of rooms, etc.) for both the dataset and individual listings.  

### 🔹 `main.ipynb`  
The **orchestrator** notebook:
1. Detects new listings.  
2. Runs them through the ML models.  
3. Identifies investment opportunities.  
4. Generates PDF reports in LaTeX.  
5. Sends the reports automatically to matching clients.  

---

## 🚀 Technologies Used  
- Python 3.x  
- Pandas, NumPy, Scikit-learn  
- Matplotlib, Seaborn  
- Jupyter Notebooks  
- LaTeX  

---

## 📊 Data Disclaimer  
- The **CSV datasets are not provided** in this repository.  
- The scraping modules are included **for educational purposes only**. For real-world applications, consider using the **official Idealista API** or other authorized data sources.
