# # Save this file as: project/src/vision/processor.py

# import cv2
# import numpy as np
# from ultralytics import YOLO

# class VisionProcessor:
#     def __init__(self):
#         """
#         Initializes the VisionProcessor, loading the YOLO model.
#         """
#         # Load the pre-trained YOLOv8 model
#         self.model = YOLO('yolov8n.pt')
#         # Define the classes of interest that should be counted as vehicles
#         self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck

#     def process_frame(self, frame, polygons):
#         """
#         Processes a single video frame to detect and count vehicles within specified polygons.

#         Args:
#             frame: The video frame (as a NumPy array) to process.
#             polygons: A list of NumPy arrays, where each array defines the vertices of a counting zone.

#         Returns:
#             A tuple containing:
#             - A list of integers representing the vehicle count in each polygon.
#             - A list of detections, where each detection is a tuple of (bounding_box, anchor_point).
#         """
#         # Initialize a list to store the count for each polygon zone
#         queue_counts = [0] * len(polygons)
        
#         # This list will store visualization data (bounding boxes and anchor points)
#         detections_for_viz = []

#         # Perform object detection on the frame
#         results = self.model(frame, verbose=False)[0]
        
#         # Iterate over each detected object
#         for box in results.boxes:
#             # Check if the detected object is a vehicle
#             if box.cls[0] in self.vehicle_classes:
#                 # Get the coordinates of the bounding box
#                 x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                
#                 # Calculate the bottom-center anchor point of the bounding box
#                 anchor_point = (int((x1 + x2) / 2), int(y2))
                
#                 # Store the data needed for visualization
#                 detections_for_viz.append(([x1, y1, x2, y2], anchor_point))

#                 # Check if the anchor point is inside any of the polygons
#                 for i, polygon in enumerate(polygons):
#                     if cv2.pointPolygonTest(polygon, anchor_point, False) >= 0:
#                         queue_counts[i] += 1
#                         # A vehicle can only be in one zone, so break the inner loop
#                         break 
        
#         return queue_counts, detections_for_viz

"""
👁️ Vision Processor & Vehicle Detection
========================================
Author: Sankalp Gaonkar (GitHub: @sankalpgaonkar)
"""

import cv2
import numpy as np
from ultralytics import YOLO
from PIL import Image

# IMPORTS for the local model
import torch
from transformers import AutoImageProcessor, AutoModelForImageClassification

class VisionProcessor:
    def __init__(self):
        """
        Initializes both the YOLO model and the local car recognition model.
        """
        # Your preferred YOLO setup
        self.model = YOLO('yolov8m.pt')
        self.vehicle_classes = [2, 3, 5, 7]  # car, motorcycle, bus, truck

        # Additions for the naming feature
        self.vehicle_cache = {} # Cache to store names of identified cars

        # --- LOAD LOCAL RECOGNITION MODEL ---
        try:
            print("Loading local car recognition model...")
            model_name = "facebook/deit-base-distilled-patch16-224"
            self.feature_extractor = AutoImageProcessor.from_pretrained(model_name)
            self.recognition_model = AutoModelForImageClassification.from_pretrained(model_name)
            print("Local car recognition model loaded successfully.")
        except Exception as e:
            print(f"⚠️ Local car recognition model skipped ({e}). Basic detection will continue.")
            self.feature_extractor = None
            self.recognition_model = None

    def get_vehicle_name_local(self, cropped_image):
        """
        Identifies the vehicle's type using a local Transformer model.
        This is the same offline function from the previous version.
        """
        if not self.recognition_model or not self.feature_extractor:
            return None
        try:
            image = Image.fromarray(cv2.cvtColor(cropped_image, cv2.COLOR_BGR2RGB))
            inputs = self.feature_extractor(images=image, return_tensors="pt")
            
            with torch.no_grad():
                outputs = self.recognition_model(**inputs)
            
            logits = outputs.logits
            predicted_class_idx = logits.argmax(-1).item()
            predicted_label = self.recognition_model.config.id2label[predicted_class_idx]
            
            car_keywords = ['car', 'jeep', 'convertible', 'coupe', 'minivan', 'limousine', 'wagon', 'racer', 'grille', 'pickup', 'suv']
            if any(keyword in predicted_label.lower() for keyword in car_keywords):
                clean_name = predicted_label.split(',')[0].title()
                print(f"Local Model Success: Identified '{clean_name}'")
                return clean_name
            return None
        except Exception as e:
            print(f"An error occurred during local vehicle recognition: {e}")
            return None

    def process_frame(self, frame, polygons):
        """
        Processes a single video frame to detect, track, count, and name vehicles.
        """
        queue_counts = [0] * len(polygons)
        detections_for_viz = []

        try:
            # Use YOLO detection (not tracking for now to ensure we get detections)
            results = self.model(frame, verbose=False)[0]
            
            # Limit how often we identify new cars to keep things fast
            process_new_car_this_frame = (cv2.getTickCount() % 25 == 0)

            # Process all detected boxes
            if results.boxes is not None and len(results.boxes) > 0:
                for i, box in enumerate(results.boxes):
                    # Get the class ID
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])

                    # Check if the class ID is a vehicle and confidence is high enough
                    if class_id in self.vehicle_classes and confidence > 0.3:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        anchor_point = (int((x1 + x2) / 2), int(y2))
                        
                        # Use detection index as tracker ID for now
                        tracker_id = i
                        
                        # This dictionary will hold the car's name
                        details = {"name": None}

                        # Try to identify the vehicle occasionally
                        if process_new_car_this_frame and i == 0:  # Only for first detection to save time
                            try:
                                cropped_car = frame[y1:y2, x1:x2]
                                if cropped_car.size > 0:  # Make sure crop is valid
                                    car_name = self.get_vehicle_name_local(cropped_car)
                                    if car_name:
                                        details["name"] = car_name
                            except:
                                pass  # Skip naming if it fails

                        # Store all data needed for visualization
                        detections_for_viz.append(([x1, y1, x2, y2], anchor_point, 'vehicle', details, tracker_id))

                        # Count vehicles in zones
                        vehicle_in_zone = False
                        for j, polygon in enumerate(polygons):
                            if cv2.pointPolygonTest(polygon, anchor_point, False) >= 0:
                                queue_counts[j] += 1
                                vehicle_in_zone = True
                                break  # Vehicle can only be in one zone
                        
                        # Debug: Log vehicles that aren't in any zone (occasionally)
                        if not vehicle_in_zone and i == 0:  # Only log for first detection
                            print(f"🔍 Vehicle at {anchor_point} not in any zone (conf: {confidence:.2f})")
            
        except Exception as e:
            print(f"Error in process_frame: {e}")
        
        return queue_counts, detections_for_viz