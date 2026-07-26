# 🧾 Receipt Intelligence System with OCR, Hybrid KIE & Text-to-SQL Agent

An end-to-end AI-powered Receipt Processing and Intelligent Querying System that extracts structured information from receipts, stores it in a database with semantic embeddings, and allows users to query their receipt history using natural language.

The project combines computer vision, OCR, hybrid information extraction, vector search, LLMs, and Text-to-SQL generation into a production-oriented pipeline.

---

# 🚀 Features

* Custom OCR pipeline trained specifically for receipt understanding.
* Fine-tuned text detection model.
* Fine-tuned text recognition model.
* Hybrid Key Information Extraction (KIE).
* Automatic receipt preprocessing and response cleaning.
* Database storage with vector embeddings.
* Semantic search over receipts.
* Intelligent Text-to-SQL agent.
* Query intent detection.
* Typo correction and query normalization.
* SQL generation with security validation.
* Modern web interface built using Flask.

---

# 📌 Project Pipeline

## 1. Dataset Collection

The dataset was created by combining:

* SROIE (Scanned Receipt OCR and Information Extraction) Dataset
* Real-world receipt images collected from Google Images

This provides a diverse collection of invoices and receipts with varying layouts, fonts, lighting conditions, and image quality.

---

## 2. Manual Annotation

All collected receipt images were manually annotated for OCR training.

The annotations include:

* Text detection bounding boxes
* Text transcription
* Key information fields

This custom annotation significantly improved model performance on real-world receipts.

---

## 3. Fine-tuned Text Detection Model

A custom Detection (DET) model was trained to accurately detect text regions on receipts.

The detector is optimized for:

* Curved text
* Small fonts
* Thermal receipts
* Multiple layouts
* Low-quality scans

---

## 4. Fine-tuned Text Recognition Model

The detected text regions are passed to a fine-tuned Recognition (REC) model which converts image regions into machine-readable text.

The recognition model is optimized for receipt-specific vocabulary including:

* Product names
* Prices
* Dates
* Invoice numbers
* Vendor names

---

## 5. Hybrid Key Information Extraction (KIE)

After OCR, a hybrid information extraction pipeline identifies important receipt fields.

### Rule-Based Extraction

Regular Expressions (Regex) are used for structured fields such as:

* Date
* Time
* Invoice Number
* Tax
* Total Amount
* Currency

### LLM-Based Semantic Extraction

A lightweight Tiny LLM extracts semantically complex fields including:

* Vendor Name
* Address
* Purchased Items
* Payment Method
* Category
* Additional metadata

This hybrid approach combines the speed of rule-based extraction with the flexibility of language models.

---

## 6. Response Cleaning

The extracted information is cleaned and normalized by:

* Removing OCR noise
* Standardizing date formats
* Normalizing currency values
* Correcting common OCR mistakes
* Removing duplicate fields
* Producing structured JSON output

---

## 7. Database Storage with Embeddings

The processed receipt data is stored in a relational database.

Additionally, semantic embeddings are generated and stored for every receipt, enabling:

* Semantic search
* Similar receipt retrieval
* Future Retrieval-Augmented Generation (RAG)
* Intelligent document lookup

---

# 🤖 Intelligent Text-to-SQL Agent

The core of the project is an AI-powered Text-to-SQL agent that converts natural language into executable SQL queries.

### Step 1 — User Query Preprocessing

The agent first processes the user's query by:

* Correcting spelling mistakes
* Fixing typos
* Normalizing text
* Understanding the intent

Example:

> "hw much did i sped on groceris last moth"

↓

> "How much did I spend on groceries last month?"

---

### Step 2 — Intent Detection

The system determines whether the query requires:

* Traditional SQL querying
* Semantic retrieval
* Hybrid SQL + Semantic Search

---

### Step 3 — SQL Generation

For standard analytical questions, the agent directly generates optimized SQL queries and retrieves results from the database.

Examples:

* Total spending this month
* Highest expense
* Vendor-wise spending
* Monthly summaries

---

### Step 4 — Semantic Search

If the query requires contextual understanding, embeddings are generated for the user's question.

The generated SQL query incorporates vector similarity search to retrieve semantically relevant receipts.

Examples:

* Receipts related to office supplies
* Purchases for client meetings
* Similar grocery purchases
* Restaurant bills with tips

---

# 🛡️ Production-Oriented Architecture

The project includes several production-ready safeguards:

* SQL Validator
* Query Security Validation
* SQL Injection Protection
* Error Handling
* Automatic Recovery Mechanisms
* Query Retry Logic
* Clean API Responses
* Robust Database Operations

---

# 🌐 Frontend

The application includes a lightweight web interface built using:

* HTML
* CSS
* JavaScript
* Flask

Users can:

* Upload receipts
* View extracted information
* Search receipts
* Ask questions in natural language
* View SQL-generated insights

---

# 🛠️ Tech Stack

### AI & Machine Learning

* Python
* OCR
* Deep Learning
* Fine-Tuned Detection Model
* Fine-Tuned Recognition Model
* Tiny LLM
* Hybrid KIE
* Embeddings

### Backend

* Flask
* SQL Database
* REST APIs

### Frontend

* HTML
* CSS
* JavaScript

### AI Components

* OCR
* Regex
* LLM
* Semantic Search
* Text-to-SQL
* Vector Embeddings

---

# 💡 Example Questions

* How much did I spend this month?
* Show all receipts from Walmart.
* What was my highest grocery bill?
* Find receipts related to electronics.
* Show restaurant expenses from last week.
* Which vendor did I spend the most money at?
* List all purchases above $100.
* Find receipts similar to my office supply purchases.

---

# 📈 Future Improvements

* Multi-language receipt support
* Receipt categorization
* Expense analytics dashboard
* RAG-powered receipt assistant
* Mobile application
* Cloud deployment
* Multi-user authentication
* Real-time receipt processing

---

# ⭐ Project Highlights

* End-to-end AI receipt understanding pipeline
* Custom-trained OCR models
* Hybrid Key Information Extraction
* Semantic search with embeddings
* Intelligent Text-to-SQL agent
* Production-ready validation and security
* Natural language querying over receipts
* Scalable architecture for enterprise expense management

---
