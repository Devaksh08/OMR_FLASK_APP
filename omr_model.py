import cv2
import numpy as np

# --- Helper Functions (Preprocessing, Reordering, etc.) ---
# These are mostly the same.

def preprocess_image(path):
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Could not read image at path: {path}")
    return cv2.resize(img, (700, 1000)) # Return the full resized image

def find_largest_rectangle(contours):
    max_area = 0
    biggest = np.array([])
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 5000:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                if area > max_area:
                    biggest = approx
                    max_area = area
    return biggest

def reorder(points):
    points = points.reshape((4, 2))
    reordered = np.zeros((4, 2), dtype=np.float32)
    add = points.sum(1)
    diff = np.diff(points, axis=1)
    reordered[0] = points[np.argmin(add)]
    reordered[3] = points[np.argmax(add)]
    reordered[1] = points[np.argmin(diff)]
    reordered[2] = points[np.argmax(diff)]
    return reordered

def get_boxes(thresh_img, rows, cols):
    boxes = []
    h, w = thresh_img.shape
    row_height = h // rows
    col_width = w // cols
    for y in range(rows):
        for x in range(cols):
            box = thresh_img[y * row_height:(y + 1) * row_height, x * col_width:(x + 1) * col_width]
            boxes.append(box)
    return boxes

def get_marked_answers(boxes, choices=5):
    # Using the robust version of this function from before
    answers = []
    num_questions = len(boxes) // choices
    for q_idx in range(num_questions):
        q_boxes = boxes[q_idx * choices : (q_idx + 1) * choices]
        filled_pixels = [cv2.countNonZero(box) for box in q_boxes]
        
        absolute_min_pixels = 150
        credible_marks = []
        for i, pixel_count in enumerate(filled_pixels):
            if pixel_count > absolute_min_pixels:
                credible_marks.append({'index': i, 'pixels': pixel_count})

        if len(credible_marks) == 0:
            answers.append(-1)
        elif len(credible_marks) == 1:
            answers.append(credible_marks[0]['index'])
        else:
            credible_marks.sort(key=lambda x: x['pixels'], reverse=True)
            strongest_mark = credible_marks[0]
            second_strongest_mark = credible_marks[1]
            if strongest_mark['pixels'] > second_strongest_mark['pixels'] * 1.5:
                answers.append(strongest_mark['index'])
            else:
                answers.append(-1)
    return answers


# --- NEW, REFACTORED CORE LOGIC ---

def get_answers_from_warped_image(warped_image, num_questions=100, num_choices=5):
    """
    Takes a pre-warped image, thresholds it, and extracts marked answers.
    This function is fully deterministic.
    """
    img_gray_warp = cv2.cvtColor(warped_image, cv2.COLOR_BGR2GRAY)
    
    # We revert to adaptiveThreshold because it's better for uneven lighting,
    # and our new pipeline structure has solved the stability problem.
    img_thresh = cv2.adaptiveThreshold(img_gray_warp, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)

    boxes = get_boxes(img_thresh, num_questions, num_choices)
    return get_marked_answers(boxes, choices=num_choices)


def evaluate_student_omr(ans_key_path, student_path, num_choices=5, num_questions=100):
    """
    Main evaluation function using the "Analyze Once, Apply to Both" strategy.
    """
    try:
        # --- Step 1: Analyze the Answer Key to get the "master" geometry ---
        key_img_resized = preprocess_image(ans_key_path)
        gray = cv2.cvtColor(key_img_resized, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 1)
        canny = cv2.Canny(blur, 10, 70)
        contours, _ = cv2.findContours(canny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        biggest_rect = find_largest_rectangle(contours)
        if biggest_rect.size == 0:
            return "Error: Could not find the OMR grid on the Answer Key. Please use a clearer image."

        # --- Step 2: Warp the Answer Key using its own geometry ---
        pts1 = reorder(biggest_rect)
        pts2 = np.float32([[0, 0], [700, 0], [0, 1000], [700, 1000]])
        matrix = cv2.getPerspectiveTransform(pts1, pts2)
        warped_key_img = cv2.warpPerspective(key_img_resized, matrix, (700, 1000))

        # --- Step 3: Extract answers from the warped key image ---
        ans = get_answers_from_warped_image(warped_key_img, num_questions, num_choices)
        if not ans:
             return "Error: Could not read bubbles from the warped Answer Key."

        # --- Step 4: Load the Student Sheet and apply the *same* transformation ---
        student_img_resized = preprocess_image(student_path)
        warped_student_img = cv2.warpPerspective(student_img_resized, matrix, (700, 1000))
        
        # --- Step 5: Extract answers from the identically warped student image ---
        stu = get_answers_from_warped_image(warped_student_img, num_questions, num_choices)
        if not stu:
            return "Error: Could not read bubbles from the warped Student Sheet."

    except Exception as e:
        return f"An unexpected error occurred: {e}"

    print(f"Answer Key:   {ans}")
    print(f"Student Resp: {stu}")
    
    min_len = min(len(ans), len(stu))
    if min_len == 0:
        return "Error: No questions could be graded."

    gradable_questions = sum(1 for a in ans if a != -1)

    if gradable_questions == 0:
        return "Score: N/A (The Answer Key has no marked answers)"

    score = sum(1 for i in range(min_len) if ans[i] != -1 and ans[i] == stu[i])
    
    accuracy = round((score / gradable_questions) * 100, 2)
    
    return f"Student Score: {score}/{gradable_questions} ({accuracy}%)"