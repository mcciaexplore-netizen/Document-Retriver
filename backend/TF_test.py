import sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --- FAKE FINANCE DATA ---
FAKE_FINANCE_DATA = [
    "Our sales in Q1 were $1.5M, a 10% increase from last year.",
    "The total revenue for Q2 dipped slightly to $1.2M due to supply chain issues.",
    "Net profit margins stood at 15% during Q1.",
    "Q3 projections indicate sales might reach $2.0M.",
    "Expenses in Q1 were unusually high, capping at $800k.",
    "Marketing budget for Q1 was heavily utilized for the new product launch.",
    "Sales in the EMEA region for Q1 accounted for 40% of total global sales.",
]

def search_tfidf(query: str, documents: list[str]) -> list[tuple[float, str]]:
    """
    Uses TF-IDF and Cosine Similarity to find the best matching documents for a query.
    Returns a list of tuples containing (match_percentage, document).
    """
    if not query or not documents:
        return []
        
    # Create the vectorizer (this automatically removes stop words and tokenizes)
    vectorizer = TfidfVectorizer(stop_words='english')
    
    # Fit the vectorizer on the documents and the query to ensure the vocabulary contains both
    all_text = documents + [query]
    try:
        tfidf_matrix = vectorizer.fit_transform(all_text)
    except ValueError:
        # If the text only contains stop words, TfidfVectorizer will throw a ValueError
        return []
        
    # The documents are rows 0 to N-1. The query is the last row.
    document_vectors = tfidf_matrix[:-1]
    query_vector = tfidf_matrix[-1]
    
    # Calculate cosine similarity between the query and all documents
    similarities = cosine_similarity(query_vector, document_vectors).flatten()
    
    results = []
    for i, score in enumerate(similarities):
        # Convert cosine similarity (0.0 to 1.0) into a percentage
        match_percentage = score * 100
        if match_percentage > 0:
            results.append((match_percentage, documents[i]))
            
    # Sort descending by match percentage
    results.sort(key=lambda x: x[0], reverse=True)
    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sample_question = " ".join(sys.argv[1:])
    else:
        sample_question = "what is the sales at Q1 ?"
        
    print(f"--- USER QUESTION ---\n{sample_question}\n")
    
    print("--- TF-IDF SEARCH RESULTS ON FAKE FINANCE DATA ---")
    matches = search_tfidf(sample_question, FAKE_FINANCE_DATA)
    
    if matches:
        for i, (pct, match) in enumerate(matches, 1):
            print(f"Result {i} ({pct:.0f}% match): {match}")
    else:
        print("No proper data found.")
