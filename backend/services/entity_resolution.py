import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from dataclasses import dataclass
from agents.discovery_agent import RawListing


@dataclass
class ResolvedResults:
    """
    The output of entity resolution:
    - exact: listings that match the user's search closely (score > 0.85)
    - related: listings that are related but not exact (score 0.60 - 0.85)
    """
    exact: list[tuple[RawListing, float]]    # (listing, similarity_score)
    related: list[tuple[RawListing, float]]


class EntityResolver:
    """
    Uses AI embeddings to figure out which listings are the same product.

    How it works:
    1. Convert every product title into a list of 384 numbers (an 'embedding')
       that captures the meaning of the title
    2. Compare the user's search query embedding to every listing's embedding
    3. If they're very similar (> 0.85), it's the same product
    4. If somewhat similar (0.60 - 0.85), it's a related product/accessory
    """

    # Load the AI model once when the app starts (not on every search)
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            print("[EntityResolver] Loading sentence-transformer model...")
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
            print("[EntityResolver] Model loaded")
        return cls._model

    def __init__(self):
        self.model = self.get_model()
        self.threshold_exact = 0.70      # above this = same product
        self.threshold_related = 0.45    # above this = related item

    def resolve(
        self,
        query: str,
        listings: list[RawListing]
    ) -> ResolvedResults:
        """
        Main method. Takes the user's query and all raw listings,
        returns them grouped into exact matches and related items.
        """
        if not listings:
            return ResolvedResults(exact=[], related=[])

        # Step 1: Turn the user's query into a vector of numbers
        query_vec = self.model.encode(
            query,
            normalize_embeddings=True    # normalization makes cosine similarity = dot product
        )

        # Step 2: Turn all listing titles into vectors
        titles = [listing.title for listing in listings]
        title_vecs = self.model.encode(
            titles,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        # Step 3: Build a FAISS index for fast comparison
        # FAISS is like a supercharged search engine for vectors
        dimension = title_vecs.shape[1]   # 384 for all-MiniLM-L6-v2
        index = faiss.IndexFlatIP(dimension)   # IP = Inner Product (= cosine on normalized vecs)
        index.add(title_vecs.astype(np.float32))

        # Step 4: Find similarity scores for ALL listings vs the query
        scores, indices = index.search(
            query_vec.reshape(1, -1).astype(np.float32),
            len(listings)
        )

        # Step 5: Group listings by their similarity score
        exact_matches = []
        related = []

        for score, idx in zip(scores[0], indices[0]):
            listing = listings[idx]
            score = float(score)

            # Attach the score to the listing so ranking can use it
            listing.similarity_score = score

            if score >= self.threshold_exact:
                exact_matches.append((listing, score))
            elif score >= self.threshold_related:
                related.append((listing, score))

        # Sort each group by score descending
        exact_matches.sort(key=lambda x: x[1], reverse=True)
        related.sort(key=lambda x: x[1], reverse=True)

        print(
            f"[EntityResolver] {len(exact_matches)} exact matches, "
            f"{len(related)} related items"
        )

        return ResolvedResults(exact=exact_matches, related=related)
