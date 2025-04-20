import pickle
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

# Load the model
with open('models/spam_model.pkl', 'rb') as model_file:
    loaded_model = pickle.load(model_file)

# Load the vectorizer
with open('models/vectorizer.pkl', 'rb') as vec_file:
    loaded_vectorizer = pickle.load(vec_file)

# Preprocessing function
def preprocess_text(text):
    text = re.sub(r'http\S+', '', text)                 # Remove hyperlinks
    text = re.sub(r'[^\w\s]', '', text)                 # Remove punctuation
    text = text.lower()                                 # Lowercase
    text = re.sub(r'\s+', ' ', text).strip()            # Remove extra spaces
    return text

# Internal prediction function
def _predict_single_text(input_text):
    processed = preprocess_text(input_text)
    vectorized = loaded_vectorizer.transform([processed])
    prediction = loaded_model.predict(vectorized)
    return prediction[0] == 0  # True if spam, False if not spam

# Public prediction function
def predict_spam(input_text):
    return _predict_single_text(input_text)