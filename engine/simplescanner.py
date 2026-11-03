import cv2
import numpy as np


class SimpleScanner:
    """
    Scanner of objects on white surface
    """

    def __init__(self):
        """
        Initialize AR markers detector
        """
        self._aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self._aruco_params = cv2.aruco.DetectorParameters()
        self._aruco_detector = cv2.aruco.ArucoDetector(self._aruco_dict, self._aruco_params)

        self._marker_top_left_id = 3
        self._marker_top_right_id = 1
        self._marker_bottom_left_id = 4
        self._marker_bottom_right_id = 2

        # Target size of scanned image in pixels
        self.target_w = 800
        self.target_h = 600

    def scan(
        self,
        frame: np.ndarray,
    ) -> np.ndarray:
        """
        Scan fish from image represented by ndarray
        :param frame: Photo of a fish from an opencv image
        :return: Aligned image of a fish
        """
        corners, ids, rejected = self._aruco_detector.detectMarkers(frame)

        top_left, top_right, bottom_right, bottom_left = None, None, None, None

        if len(corners) > 0:
            ids = ids.flatten()
            for marker_corner, marker_id in zip(corners, ids, strict=True):
                corners = marker_corner.reshape((4, 2))
                if marker_id == self._marker_top_left_id:
                    top_left, _, _, _ = corners
                elif marker_id == self._marker_top_right_id:
                    _, top_right, _, _ = corners
                elif marker_id == self._marker_bottom_right_id:
                    _, _, bottom_right, _ = corners
                elif marker_id == self._marker_bottom_left_id:
                    _, _, _, bottom_left = corners

        if (top_left is None) or (top_right is None) or (bottom_right is None) or (bottom_left is None):
            raise ValueError("Markers in the image are not found")
        else:
            tr = (int(top_right[0]), int(top_right[1]))
            br = (int(bottom_right[0]), int(bottom_right[1]))
            bl = (int(bottom_left[0]), int(bottom_left[1]))
            tl = (int(top_left[0]), int(top_left[1]))

            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))

            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))

            dst = np.array(
                [[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32"
            )

            rect = np.array((tl, tr, br, bl)).astype("float32")
            M = cv2.getPerspectiveTransform(rect, dst)
            warped = cv2.warpPerspective(frame, M, (maxWidth, maxHeight))

            return warped

    def remove_background(
        self,
        frame: np.ndarray,
    ) -> np.ndarray:
        """
        Remove background from the fish image
        :param frame: Aligned image of a fish
        :return: OpenCV image with alpha channel
        """
        frame = cv2.resize(frame, (self.target_w, self.target_h))

        # Convert to grayscale with better handling of red channel
        b, g, r = cv2.split(frame)
        # Give more weight to red channel
        gray = cv2.addWeighted(cv2.addWeighted(b, 0.299, g, 0.587, 0), 0.4, r, 0.6, 0)

        # Create binary mask using adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, blockSize=25, C=3
        )

        # Find contours before removing AR markers
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Create alpha channel
        alpha = np.zeros_like(gray)

        if contours:
            # Find the largest contour (should be the fish)
            largest_contour = max(contours, key=cv2.contourArea)

            # Create filled mask from contour
            cv2.drawContours(alpha, [largest_contour], -1, 255, -1)

            # Clean up the mask
            kernel = np.ones((3, 3), np.uint8)
            alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)

            # Dilate slightly to prevent edge cutting
            alpha = cv2.dilate(alpha, kernel, iterations=2)

            # Create a gradient mask for smoother transitions
            gradient_kernel = np.ones((5, 5), np.uint8)
            gradient_mask = cv2.morphologyEx(alpha, cv2.MORPH_GRADIENT, gradient_kernel)

            # Remove AR markers after contour detection, with smaller area and smoother transition
            marker_size = 110  # Further reduced from 120
            padding = 15  # Increased padding
            gradient_width = 5  # Width of gradient transition

            def create_marker_mask(x, y, w, h):
                mask = np.ones_like(alpha) * 255
                # Create outer and inner rectangles for gradient
                cv2.rectangle(mask, (x + padding, y + padding), (x + w - padding, y + h - padding), 128, -1)
                cv2.rectangle(
                    mask,
                    (x + padding + gradient_width, y + padding + gradient_width),
                    (x + w - padding - gradient_width, y + h - padding - gradient_width),
                    0,
                    -1,
                )
                # Blur the mask to create a gradient
                mask = cv2.GaussianBlur(mask, (5, 5), 0)
                return mask

            # Apply marker masks with gradient
            marker_positions = [
                (0, 0),  # Top-left
                (self.target_w - marker_size, 0),  # Top-right
                (self.target_w - marker_size, self.target_h - marker_size),  # Bottom-right
                (0, self.target_h - marker_size),  # Bottom-left
            ]

            # Combine all marker masks
            combined_mask = np.ones_like(alpha) * 255
            for x, y in marker_positions:
                marker_mask = create_marker_mask(x, y, marker_size, marker_size)
                combined_mask = cv2.min(combined_mask, marker_mask)

            # Apply combined mask with gradient preservation
            alpha = cv2.multiply(alpha, combined_mask, scale=1 / 255)

            # Preserve strong edges from original detection
            edge_preserve = cv2.bitwise_and(alpha, gradient_mask)
            alpha = cv2.add(alpha, edge_preserve)

            # Ensure binary mask (no partial transparency)
            _, alpha = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)

        # Create RGBA image
        filtered_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA)

        # Set alpha channel
        filtered_frame[..., 3] = alpha

        # Ensure complete transparency where alpha is 0
        filtered_frame[alpha == 0] = [0, 0, 0, 0]

        # Ensure solid opacity where fish is present
        filtered_frame[alpha == 255, 3] = 255

        return filtered_frame


"""
if __name__ == '__main__':
    scanner = SimpleScanner()
    files = glob('/home/david/PycharmProjects/FishScanner/photos/*.jpg')
    for filename in files:
        frame = cv2.imread(filename)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        processed_frame = scanner.scan(frame)
        processed_frame = scanner.remove_background(processed_frame)

        cv2.imshow('fish', processed_frame)
        cv2.waitKey(0)
"""
