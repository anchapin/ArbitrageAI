"""
Task Classifier Module.

ML-based task classifier using embeddings and clustering for intelligent task routing.
"""

from collections import defaultdict
from pathlib import Path
import pickle  # noqa: S403 - Used for internal model storage, not untrusted data
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score

from src.utils.logger import get_logger
from src.agent_execution.models import TaskProfile

logger = get_logger(__name__)


class TaskClassifier:
    """
    ML-based task classifier using embeddings and clustering.

    Uses multiple classification approaches:
    1. Text-based classification using TF-IDF and Random Forest
    2. Clustering-based classification using K-means
    3. Rule-based classification for known patterns
    """

    def __init__(self, model_path: str | None = None):
        """
        Initialize the task classifier.

        Args:
            model_path: Optional path to load pre-trained models
        """
        self.model_path = model_path or self._get_default_model_path()
        self.text_classifier = None
        self.clustering_model = None
        self.vectorizer = None
        self.label_encoder = None
        self.is_trained = False

        self.classification_metrics = defaultdict(list)
        self._load_models()

    @staticmethod
    def _get_default_model_path() -> str:
        """Get default model storage path."""
        return str(Path(__file__).parent / "models" / "task_classifier.pkl")

    def _load_models(self):
        """Load pre-trained models from disk."""
        try:
            if Path(self.model_path).exists():
                with open(self.model_path, "rb") as f:
                    models = pickle.load(f)  # noqa: S301 - Safe: loading internal models, not untrusted data
                    self.text_classifier = models.get("classifier")
                    self.clustering_model = models.get("clustering")
                    self.vectorizer = models.get("vectorizer")
                    self.label_encoder = models.get("label_encoder")
                    self.is_trained = models.get("is_trained", False)
                logger.info("Loaded pre-trained task classification models")
            else:
                logger.info("No pre-trained models found, will train on first use")
        except (pickle.UnpicklingError, EOFError, FileNotFoundError, OSError, ValueError, TypeError) as e:
            logger.warning(f"Failed to load models: {e}", exc_info=True)
        except Exception as e:
            logger.warning(f"Failed to load models: {e}", exc_info=True)

    def _save_models(self):
        """Save trained models to disk."""
        try:
            Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
            models = {
                "classifier": self.text_classifier,
                "clustering": self.clustering_model,
                "vectorizer": self.vectorizer,
                "label_encoder": self.label_encoder,
                "is_trained": self.is_trained,
            }
            with open(self.model_path, "wb") as f:
                pickle.dump(models, f)
            logger.info("Saved task classification models")
        except (OSError, ValueError, TypeError) as e:
            logger.error(f"Failed to save models: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Failed to save models: {e}", exc_info=True)

    def extract_features(self, task_profiles: list[TaskProfile]) -> np.ndarray:
        """
        Extract features from task profiles for ML classification.

        Args:
            task_profiles: List of task profiles

        Returns:
            Feature matrix
        """
        text_data = []
        for profile in task_profiles:
            text_features = f"{profile.domain} {profile.user_request} {' '.join(profile.csv_headers)}"
            text_data.append(text_features)

        if self.vectorizer is None:
            self.vectorizer = TfidfVectorizer(
                max_features=1000,
                stop_words="english",
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.8,
            )
            text_features = self.vectorizer.fit_transform(text_data)
        else:
            text_features = self.vectorizer.transform(text_data)

        numerical_features = np.array([
            [
                profile.complexity_score,
                profile.estimated_time,
                profile.success_rate,
                profile.retry_count,
                profile.review_attempts,
            ]
            for profile in task_profiles
        ])

        if text_features.shape[0] > 0:
            combined_features = np.hstack([text_features.toarray(), numerical_features])
        else:
            combined_features = numerical_features

        return combined_features

    def train(self, task_profiles: list[TaskProfile], labels: list[str]):
        """
        Train the task classifier using historical data.

        Args:
            task_profiles: List of task profiles with features
            labels: Corresponding labels (handler types)
        """
        logger.info(f"Training task classifier with {len(task_profiles)} samples")

        features = self.extract_features(task_profiles)

        self.text_classifier = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42, class_weight="balanced",
        )
        self.text_classifier.fit(features, labels)

        self.clustering_model = KMeans(
            n_clusters=min(5, len(set(labels))), random_state=42,
        )
        self.clustering_model.fit(features)

        self.is_trained = True
        self._save_models()

        predictions = self.text_classifier.predict(features)
        accuracy = accuracy_score(labels, predictions)
        logger.info(f"Training accuracy: {accuracy:.3f}")

        self.classification_metrics["training_accuracy"].append(accuracy)

    def classify(self, task_profile: TaskProfile) -> dict[str, Any]:
        """
        Classify a task and return routing recommendations.

        Args:
            task_profile: Task profile to classify

        Returns:
            Dictionary with classification results
        """
        if not self.is_trained:
            return self._rule_based_classification(task_profile)

        try:
            features = self.extract_features([task_profile])
            probabilities = self.text_classifier.predict_proba(features)[0]
            predicted_class = self.text_classifier.predict(features)[0]
            cluster = self.clustering_model.predict(features)[0]
            confidence = max(probabilities)

            top_indices = np.argsort(probabilities)[-3:][::-1]
            top_predictions = [
                {
                    "handler": self.text_classifier.classes_[i],
                    "probability": probabilities[i],
                }
                for i in top_indices
            ]

            return {
                "predicted_handler": predicted_class,
                "confidence": confidence,
                "top_predictions": top_predictions,
                "cluster": int(cluster),
                "anomaly_score": self._calculate_anomaly_score(features, cluster),
                "method": "ml_classification",
            }

        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.warning(f"ML classification error: {e}, falling back to rule-based", exc_info=True)
            return self._rule_based_classification(task_profile)
        except Exception as e:
            logger.warning(f"ML classification failed: {e}, falling back to rule-based", exc_info=True)
            return self._rule_based_classification(task_profile)

    @staticmethod
    def _rule_based_classification(task_profile: TaskProfile) -> dict[str, Any]:
        """Fallback rule-based classification for untrained models."""
        from collections import Counter

        domain_rules = {
            "legal": ["legal_specialist", "document_generator"],
            "accounting": ["accounting_specialist", "spreadsheet_generator"],
            "data_analysis": ["visualization_specialist", "report_generator"],
        }

        complexity_rules = {
            "high": ["expert_handler", "cloud_model"],
            "medium": ["standard_handler", "local_model"],
            "low": ["basic_handler", "template_based"],
        }

        format_rules = {
            "docx": ["document_generator", "legal_specialist"],
            "xlsx": ["spreadsheet_generator", "accounting_specialist"],
            "pdf": ["document_generator", "report_generator"],
            "image": ["visualization_specialist", "standard_handler"],
        }

        candidates = []

        if task_profile.domain in domain_rules:
            candidates.extend(domain_rules[task_profile.domain])

        if task_profile.complexity_score > 0.7:
            candidates.extend(complexity_rules["high"])
        elif task_profile.complexity_score > 0.4:
            candidates.extend(complexity_rules["medium"])
        else:
            candidates.extend(complexity_rules["low"])

        if task_profile.output_format in format_rules:
            candidates.extend(format_rules[task_profile.output_format])

        candidate_counts = Counter(candidates)
        top_candidates = candidate_counts.most_common(3)

        return {
            "predicted_handler": top_candidates[0][0] if top_candidates else "standard_handler",
            "confidence": 0.5,
            "top_predictions": [
                {"handler": handler, "probability": count / len(candidates)}
                for handler, count in top_candidates
            ],
            "cluster": -1,
            "anomaly_score": 0.0,
            "method": "rule_based",
        }

    def _calculate_anomaly_score(self, features: np.ndarray, cluster: int) -> float:
        """Calculate anomaly score for a task profile."""
        try:
            center = self.clustering_model.cluster_centers_[cluster]
            distance = np.linalg.norm(features[0] - center)

            max_distance = np.max(
                [np.linalg.norm(features[0] - c) for c in self.clustering_model.cluster_centers_],
            )

            return min(distance / max_distance if max_distance > 0 else 0.0, 1.0)
        except (ValueError, TypeError, ZeroDivisionError, KeyError, IndexError) as e:
            logger.debug(f"Anomaly score calculation error: {e}", exc_info=True)
            return 0.0
        except Exception as e:
            logger.debug(f"Anomaly score calculation failed: {e}", exc_info=True)
            return 0.0
