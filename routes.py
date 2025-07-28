import os
import uuid
from flask import Blueprint, render_template, request, flash, current_app
from werkzeug.utils import secure_filename
from .omr_model import evaluate_student_omr

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        if 'answer_key' not in request.files or 'student_key' not in request.files:
            flash('Both answer key and student sheet files are required.', 'danger')
            return render_template('index.html', result=result)

        answer_key = request.files['answer_key']
        student_key = request.files['student_key']

        if answer_key.filename == '' or student_key.filename == '':
            flash('Both files must be selected.', 'danger')
            return render_template('index.html', result=result)

        if answer_key and student_key and allowed_file(answer_key.filename) and allowed_file(student_key.filename):
            ans_secure_fn = secure_filename(answer_key.filename)
            stu_secure_fn = secure_filename(student_key.filename)
            unique_ans_fn = f"answer_{uuid.uuid4().hex}_{ans_secure_fn}"
            unique_stu_fn = f"student_{uuid.uuid4().hex}_{stu_secure_fn}"

            upload_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'])
            
            answer_key_path = os.path.join(upload_path, unique_ans_fn)
            student_key_path = os.path.join(upload_path, unique_stu_fn)
            
            answer_key.save(answer_key_path)
            student_key.save(student_key_path)

            try:
                result = evaluate_student_omr(answer_key_path, student_key_path)
                if result and not result.startswith("Error"):
                     flash(result, 'success')
                     result = None
                else:
                     flash(result, 'danger')
                     result = None

            except Exception as e:
                flash(f"An unexpected error occurred during processing: {e}", "danger")
                result = None
            finally:
                if os.path.exists(answer_key_path):
                    os.remove(answer_key_path)
                if os.path.exists(student_key_path):
                    os.remove(student_key_path)

        else:
            flash('Invalid file type. Please upload images (png, jpg, jpeg).', 'danger')

    return render_template('index.html', result=result)