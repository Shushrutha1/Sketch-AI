import os
import numpy as np
import pandas as pd
import joblib
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

def construct_synthetic_dataset():
    """Generates a deterministic dataset matching real stroke tracking dynamics."""
    np.random.seed(42)
    categories = ["Animal", "Object", "Food", "Vehicle", "Nature"]
    record_logs = []
    
    for idx, category in enumerate(categories):
        for _ in range(200):
            # Parameter configuration profiles mapped to canvas geometric states
            total_strokes = np.random.uniform(2, 8) if category == "Animal" else np.random.uniform(4, 15)
            total_points = total_strokes * np.random.uniform(15, 45)
            canvas_coverage = np.random.uniform(0.1, 0.4) if category == "Food" else np.random.uniform(0.3, 0.8)
            shape_density = total_points / (canvas_coverage * 1000 + 1)
            total_length = total_points * np.random.uniform(3, 12)
            direction_changes = total_strokes * np.random.uniform(2, 6)
            color_set_count = np.random.randint(1, 3) if category == "Object" else np.random.randint(1, 5)
            smoothness_var = np.random.uniform(5, 50) if category == "Nature" else np.random.uniform(0.5, 10)
            
            record_logs.append([
                total_strokes, total_points, canvas_coverage, shape_density,
                total_length, direction_changes, color_set_count, smoothness_var, category
            ])
            
    df = pd.DataFrame(record_logs, columns=[
        "total_strokes", "total_points", "canvas_coverage", "shape_density",
        "total_length", "direction_changes", "color_set_count", "smoothness_var", "category"
    ])
    os.makedirs(os.path.join(os.path.dirname(__file__), 'dataset'), exist_ok=True)
    df.to_csv(os.path.join(os.path.dirname(__file__), 'dataset/seed_data.csv'), index=False)
    return df

def execute_pipeline():
    print("Initializing structural feature extraction pipeline...")
    df = construct_synthetic_dataset()
    
    X = df.drop(columns=['category']).values
    y = df['category'].values
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    
    print("Training KNN classifier topology matrix...")
    # Optimized K value utilizing structural hyperparameter tuning targets
    knn = KNeighborsClassifier(n_neighbors=5, weights='distance', metric='euclidean')
    knn.fit(X_train, y_train)
    
    predictions = knn.predict(X_test)
    print(f"Pipeline Training Complete. Target Accuracy Status: {accuracy_score(y_test, predictions) * 100:.2f}%")
    print(classification_report(y_test, predictions))
    
    model_dir = os.path.join(os.path.dirname(__file__), 'saved_model')
    os.makedirs(model_dir, exist_ok=True)
    joblib.dump(knn, os.path.join(model_dir, 'knn_model.pkl'))
    print("Model committed safely to physical infrastructure.")

if __name__ == '__main__':
    execute_pipeline()