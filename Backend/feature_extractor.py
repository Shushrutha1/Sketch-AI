import numpy as np

class FeatureExtractor:
    @staticmethod
    def process_canvas_payload(stroke_history):
        """
        Transforms raw client stroke logs into a vector configuration space.
        Features extracted match ML parameters exactly.
        """
        if not stroke_history or len(stroke_history) == 0:
            return [0.0] * 8

        total_strokes = len(stroke_history)
        all_points = []
        direction_changes = 0
        color_set = set()
        total_length = 0.0

        for stroke in stroke_history:
            points = stroke.get('points', [])
            color_set.add(stroke.get('color', '#ffffff'))
            if len(points) < 2:
                continue
                
            prev_p = points[0]
            all_points.append(prev_p)
            prev_dx, prev_dy = 0.0, 0.0

            for i, p in enumerate(points[1:], start=1):
                all_points.append(p)
                dx = p[0] - prev_p[0]
                dy = p[1] - prev_p[1]
                total_length += np.sqrt(dx**2 + dy**2)
                
                if i > 1:
                    if (dx > 0 and prev_dx < 0) or (dx < 0 and prev_dx > 0) or \
                       (dy > 0 and prev_dy < 0) or (dy < 0 and prev_dy > 0):
                        direction_changes += 1
                prev_dx, prev_dy = dx, dy
                prev_p = p

        if len(all_points) == 0:
            return [float(total_strokes), 0.0, 0.0, 0.0, 0.0, 0.0, float(len(color_set)), 1.0]

        x_coords = [p[0] for p in all_points]
        y_coords = [p[1] for p in all_points]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        width = max_x - min_x
        height = max_y - min_y
        
        canvas_coverage = (width * height) / (800.0 * 450.0) # Evaluated target envelope parameters
        shape_density = len(all_points) / ((width * height) + 1.0)
        smoothness_var = np.var(np.diff(x_coords)) if len(x_coords) > 2 else 0.0

        return [
            float(total_strokes),
            float(len(all_points)),
            float(canvas_coverage),
            float(shape_density),
            float(total_length),
            float(direction_changes),
            float(len(color_set)),
            float(smoothness_var)
        ]