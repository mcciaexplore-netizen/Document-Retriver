import itertools
import random
import re

# Dictionary of punctuation marks and their English meaning
PUNCTUATION_DICT = {
    "?": "question mark",
    "!": "exclamation mark",
    ".": "period",
    ",": "comma",
    ";": "semicolon",
    ":": "colon",
    "-": "hyphen",
    "(": "left parenthesis",
    ")": "right parenthesis",
    "[": "left bracket",
    "]": "right bracket",
    "{": "left brace",
    "}": "right brace",
    "'": "single quote",
    "\"": "double quote"
}

def generate_optimized_queries(user_question: str, num_queries_to_return: int = 5) -> list[str]:
    """
    Breaks a user question into values, selects keywords and a mandatory punctuation mark,
    and creates combinations/permutations of them to generate a search list.
    """
    # 1. Break the question into an array of words
    words = [word.strip() for word in re.split(r'\W+', user_question) if word.strip()]
    
    # 2. Extract punctuation marks used in the question
    punctuations_in_question = [char for char in user_question if char in PUNCTUATION_DICT]
    
    # 3. Select a mandatory punctuation mark (default to '?' if none found)
    mandatory_punct = punctuations_in_question[0] if punctuations_in_question else "?"
    
    # 4. Filter out common stop words to randomly select meaningful keywords
    stop_words = {"what", "is", "the", "at", "in", "on", "a", "an", "of", "to", "for", "by", "with"}
    keywords = [w for w in words if w.lower() not in stop_words]
    
    if not keywords:
        keywords = words  # Fallback if the question is only stop words
        
    generated_queries = []
    
    # 5. Create combinations and permutations of the keywords
    # For example, if keywords are ['sales', 'Q1'], permutations are ('sales',), ('Q1',), ('sales', 'Q1'), ('Q1', 'sales')
    for r in range(1, len(keywords) + 1):
        for combo in itertools.permutations(keywords, r):
            # 6. Combine the arbitrary permutations with the mandatory punctuation
            query_string = " ".join(combo) + f" {mandatory_punct}"
            generated_queries.append(query_string)
            
    # Remove duplicates and shuffle to randomly select arbitrary combinations
    generated_queries = list(set(generated_queries))
    random.shuffle(generated_queries)
    
    # Return a subset of the generated queries
    return generated_queries[:num_queries_to_return]

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

def search_fake_data(query: str) -> list[tuple[float, str]]:
    """
    A simple heuristic search that checks how many words from the query
    exist in each sentence of the fake data. Returns the best matches
    along with their match percentage. Filters out results below 25%.
    """
    # Remove punctuation for simple matching
    clean_query = re.sub(r'\W+', ' ', query).strip().lower()
    query_words = set(clean_query.split())
    if not query_words:
        return []
        
    results = []
    for sentence in FAKE_FINANCE_DATA:
        clean_sentence = re.sub(r'\W+', ' ', sentence).lower()
        sentence_words = set(clean_sentence.split())
        
        # Calculate how many query words match
        match_count = len(query_words.intersection(sentence_words))
        
        # Calculate match percentage (based on how many words in the query matched)
        match_percentage = (match_count / len(query_words)) * 100 if len(query_words) > 0 else 0
        
        # Only keep matches that are 25% or greater
        if match_percentage >= 25.0:
            results.append((match_percentage, sentence))
            
    # Sort by match percentage descending
    results.sort(key=lambda x: x[0], reverse=True)
    return results

if __name__ == "__main__":
    import sys
    
    # Allow the user to pass the question via command-line arguments
    if len(sys.argv) > 1:
        sample_question = " ".join(sys.argv[1:])
    else:
        sample_question = "what is the sales at Q1 ?"
        
    print(f"--- USER QUESTION ---\n{sample_question}\n")
    
    queries = generate_optimized_queries(sample_question, num_queries_to_return=10)
    
    print("--- GENERATED SEARCH QUERIES ---")
    for i, query in enumerate(queries, 1):
        print(f"{i}. {query}")
        
    print("\n--- HEURISTIC SEARCH RESULTS ON FAKE FINANCE DATA ---")
    # We will pick the longest permutation query (usually contains the most keywords) to test
    # Or we can just run the search on the first generated query
    best_query = max(queries, key=len) if queries else ""
    print(f"Testing search using query permutation: '{best_query}'")
    
    matches = search_fake_data(best_query)
    
    if matches:
        for i, (pct, match) in enumerate(matches, 1):
            print(f"Result {i} ({pct:.0f}% match): {match}")
    else:
        print("No proper data found (no results met the 25% match threshold).")
