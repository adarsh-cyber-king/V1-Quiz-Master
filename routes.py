from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import func, desc
import json
from datetime import datetime, date, timedelta
from functools import wraps

from app import db
from models import User, Subject, Chapter, Quiz, Question, Score
from forms import (
    LoginForm, RegistrationForm, SubjectForm, ChapterForm, 
    QuizForm, QuestionForm, QuizAttemptForm, SearchForm
)

# Create blueprints
auth_bp = Blueprint('auth', __name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
user_bp = Blueprint('user', __name__, url_prefix='/user')

# Admin required decorator
def admin_required(f):
    """Decorator to require admin role for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions for stats
def get_dashboard_stats():
    """Get statistics for the admin dashboard"""
    total_users = User.query.count()
    total_subjects = Subject.query.count()
    total_quizzes = Quiz.query.count()
    total_questions = Question.query.count()
    
    # Recent quizzes
    recent_quizzes = Quiz.query.order_by(Quiz.created_at.desc()).limit(5).all()
    
    # Recent scores
    recent_scores = Score.query.order_by(Score.time_stamp.desc()).limit(5).all()
    
    # Average scores by quiz
    quiz_stats = []
    quizzes = Quiz.query.all()
    for quiz in quizzes:
        scores = Score.query.filter_by(quiz_id=quiz.id).all()
        if scores:
            avg_score = sum(score.percentage() for score in scores) / len(scores)
            attempts = len(scores)
        else:
            avg_score = 0
            attempts = 0
        
        quiz_stats.append({
            'quiz': quiz,
            'avg_score': round(avg_score, 2),
            'attempts': attempts
        })
    
    # Sort by attempts
    quiz_stats.sort(key=lambda x: x['attempts'], reverse=True)
    
    return {
        'total_users': total_users,
        'total_subjects': total_subjects,
        'total_quizzes': total_quizzes,
        'total_questions': total_questions,
        'recent_quizzes': recent_quizzes,
        'recent_scores': recent_scores,
        'quiz_stats': quiz_stats[:5]  # Top 5 quizzes
    }

def get_user_stats(user_id):
    """Get statistics for the user dashboard"""
    # Get user's scores
    user_scores = Score.query.filter_by(user_id=user_id).all()
    
    # Calculate average percentage
    if user_scores:
        avg_percentage = sum(score.percentage() for score in user_scores) / len(user_scores)
    else:
        avg_percentage = 0
    
    # Get completed quizzes
    completed_quizzes = len(user_scores)
    
    # Get total available quizzes
    total_quizzes = Quiz.query.count()
    
    # Get recent scores
    recent_scores = Score.query.filter_by(user_id=user_id).order_by(Score.time_stamp.desc()).limit(5).all()
    
    # Get upcoming quizzes
    upcoming_quizzes = Quiz.query.filter(Quiz.date_of_quiz >= date.today()).order_by(Quiz.date_of_quiz).limit(5).all()
    
    # Calculate scores by subject
    subject_scores = {}
    for score in user_scores:
        quiz = Quiz.query.get(score.quiz_id)
        chapter = Chapter.query.get(quiz.chapter_id)
        subject = Subject.query.get(chapter.subject_id)
        
        if subject.name not in subject_scores:
            subject_scores[subject.name] = {
                'scores': [],
                'total': 0,
                'count': 0
            }
        
        subject_scores[subject.name]['scores'].append(score.percentage())
        subject_scores[subject.name]['total'] += score.percentage()
        subject_scores[subject.name]['count'] += 1
    
    # Calculate averages for each subject
    subject_avg = {}
    for subject, data in subject_scores.items():
        subject_avg[subject] = round(data['total'] / data['count'], 2) if data['count'] > 0 else 0
    
    return {
        'avg_percentage': round(avg_percentage, 2),
        'completed_quizzes': completed_quizzes,
        'completion_rate': round((completed_quizzes / total_quizzes) * 100, 2) if total_quizzes > 0 else 0,
        'recent_scores': recent_scores,
        'upcoming_quizzes': upcoming_quizzes,
        'subject_avg': subject_avg
    }

# Auth routes
@auth_bp.route('/')
def index():
    return render_template('auth/index.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('user.user_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if user.is_admin:
                return redirect(next_page or url_for('admin.dashboard'))
            else:
                return redirect(next_page or url_for('user.user_dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            username=form.username.data,
            full_name=form.full_name.data,
            qualification=form.qualification.data,
            dob=form.dob.data,
            is_admin=False
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.index'))

# Admin routes
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    stats = get_dashboard_stats()
    return render_template('admin/dashboard.html', stats=stats, Chapter=Chapter, User=User, Quiz=Quiz, Subject=Subject)

@admin_bp.route('/subjects', methods=['GET', 'POST'])
@login_required
@admin_required
def subjects():
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(name=form.name.data, description=form.description.data)
        db.session.add(subject)
        db.session.commit()
        flash('Subject has been created!', 'success')
        return redirect(url_for('admin.subjects'))
    
    subjects = Subject.query.order_by(Subject.name).all()
    return render_template('admin/subjects.html', subjects=subjects, form=form)

@admin_bp.route('/subjects/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_subject(id):
    subject = Subject.query.get_or_404(id)
    form = SubjectForm()
    
    if form.validate_on_submit():
        subject.name = form.name.data
        subject.description = form.description.data
        db.session.commit()
        flash('Subject has been updated!', 'success')
        return redirect(url_for('admin.subjects'))
    
    elif request.method == 'GET':
        form.name.data = subject.name
        form.description.data = subject.description
    
    return render_template('admin/edit_subject.html', form=form, subject=subject)

@admin_bp.route('/subjects/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_subject(id):
    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
    db.session.commit()
    flash('Subject has been deleted!', 'success')
    return redirect(url_for('admin.subjects'))

@admin_bp.route('/chapters', methods=['GET', 'POST'])
@login_required
@admin_required
def chapters():
    form = ChapterForm()
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.order_by(Subject.name).all()]
    
    if form.validate_on_submit():
        chapter = Chapter(
            name=form.name.data,
            description=form.description.data,
            subject_id=form.subject_id.data
        )
        db.session.add(chapter)
        db.session.commit()
        flash('Chapter has been created!', 'success')
        return redirect(url_for('admin.chapters'))
    
    chapters = Chapter.query.order_by(Chapter.name).all()
    return render_template('admin/chapters.html', chapters=chapters, form=form, Subject=Subject, Chapter=Chapter)

@admin_bp.route('/chapters/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_chapter(id):
    chapter = Chapter.query.get_or_404(id)
    form = ChapterForm()
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.order_by(Subject.name).all()]
    
    if form.validate_on_submit():
        chapter.name = form.name.data
        chapter.description = form.description.data
        chapter.subject_id = form.subject_id.data
        db.session.commit()
        flash('Chapter has been updated!', 'success')
        return redirect(url_for('admin.chapters'))
    
    elif request.method == 'GET':
        form.name.data = chapter.name
        form.description.data = chapter.description
        form.subject_id.data = chapter.subject_id
    
    return render_template('admin/edit_chapter.html', form=form, chapter=chapter)

@admin_bp.route('/chapters/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_chapter(id):
    chapter = Chapter.query.get_or_404(id)
    db.session.delete(chapter)
    db.session.commit()
    flash('Chapter has been deleted!', 'success')
    return redirect(url_for('admin.chapters'))

@admin_bp.route('/quizzes', methods=['GET', 'POST'])
@login_required
@admin_required
def quizzes():
    form = QuizForm()
    form.chapter_id.choices = [(c.id, f"{c.name} ({Subject.query.get(c.subject_id).name})") 
                               for c in Chapter.query.order_by(Chapter.name).all()]
    
    if form.validate_on_submit():
        quiz = Quiz(
            title=form.title.data,
            chapter_id=form.chapter_id.data,
            date_of_quiz=form.date_of_quiz.data,
            time_duration=form.time_duration.data,
            remarks=form.remarks.data
        )
        db.session.add(quiz)
        db.session.commit()
        flash('Quiz has been created!', 'success')
        return redirect(url_for('admin.quizzes'))
    
    quizzes = Quiz.query.order_by(Quiz.date_of_quiz.desc()).all()
    return render_template('admin/quizzes.html', quizzes=quizzes, form=form, Chapter=Chapter, Subject=Subject, Quiz=Quiz)

@admin_bp.route('/quizzes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_quiz(id):
    quiz = Quiz.query.get_or_404(id)
    form = QuizForm()
    form.chapter_id.choices = [(c.id, f"{c.name} ({Subject.query.get(c.subject_id).name})") 
                               for c in Chapter.query.order_by(Chapter.name).all()]
    
    if form.validate_on_submit():
        quiz.title = form.title.data
        quiz.chapter_id = form.chapter_id.data
        quiz.date_of_quiz = form.date_of_quiz.data
        quiz.time_duration = form.time_duration.data
        quiz.remarks = form.remarks.data
        db.session.commit()
        flash('Quiz has been updated!', 'success')
        return redirect(url_for('admin.quizzes'))
    
    elif request.method == 'GET':
        form.title.data = quiz.title
        form.chapter_id.data = quiz.chapter_id
        form.date_of_quiz.data = quiz.date_of_quiz
        form.time_duration.data = quiz.time_duration
        form.remarks.data = quiz.remarks
    
    return render_template('admin/edit_quiz.html', form=form, quiz=quiz)

@admin_bp.route('/quizzes/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_quiz(id):
    quiz = Quiz.query.get_or_404(id)
    db.session.delete(quiz)
    db.session.commit()
    flash('Quiz has been deleted!', 'success')
    return redirect(url_for('admin.quizzes'))

@admin_bp.route('/quizzes/<int:id>/questions', methods=['GET', 'POST'])
@login_required
@admin_required
def questions(id):
    quiz = Quiz.query.get_or_404(id)
    chapter = Chapter.query.get(quiz.chapter_id)
    form = QuestionForm()
    
    if form.validate_on_submit():
        question = Question(
            quiz_id=quiz.id,
            question_text=form.question_text.data,
            option_1=form.option_1.data,
            option_2=form.option_2.data,
            option_3=form.option_3.data,
            option_4=form.option_4.data,
            correct_option=form.correct_option.data
        )
        db.session.add(question)
        db.session.commit()
        flash('Question has been added!', 'success')
        return redirect(url_for('admin.questions', id=quiz.id))
    
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    return render_template('admin/questions.html', quiz=quiz, questions=questions, form=form, chapter=chapter)

@admin_bp.route('/questions/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_question(id):
    question = Question.query.get_or_404(id)
    form = QuestionForm()
    
    if form.validate_on_submit():
        question.question_text = form.question_text.data
        question.option_1 = form.option_1.data
        question.option_2 = form.option_2.data
        question.option_3 = form.option_3.data
        question.option_4 = form.option_4.data
        question.correct_option = form.correct_option.data
        db.session.commit()
        flash('Question has been updated!', 'success')
        return redirect(url_for('admin.questions', id=question.quiz_id))
    
    elif request.method == 'GET':
        form.question_text.data = question.question_text
        form.option_1.data = question.option_1
        form.option_2.data = question.option_2
        form.option_3.data = question.option_3
        form.option_4.data = question.option_4
        form.correct_option.data = question.correct_option
    
    return render_template('admin/edit_question.html', form=form, question=question)

@admin_bp.route('/questions/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_question(id):
    question = Question.query.get_or_404(id)
    quiz_id = question.quiz_id
    db.session.delete(question)
    db.session.commit()
    flash('Question has been deleted!', 'success')
    return redirect(url_for('admin.questions', id=quiz_id))

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.filter(User.id != current_user.id).order_by(User.username).all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/<int:id>/scores')
@login_required
@admin_required
def user_scores(id):
    user = User.query.get_or_404(id)
    scores = Score.query.filter_by(user_id=user.id).order_by(Score.time_stamp.desc()).all()
    return render_template('admin/user_scores.html', user=user, scores=scores, Quiz=Quiz)

# User routes
@user_bp.route('/dashboard')
@login_required
def user_dashboard():
    from datetime import date
    stats = get_user_stats(current_user.id)
    subjects = Subject.query.all()
    return render_template('user/dashboard.html', stats=stats, subjects=subjects, Chapter=Chapter, Quiz=Quiz, date=date)

@user_bp.route('/subjects/<int:subject_id>/chapters')
@login_required
def subject_chapters(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    chapters = Chapter.query.filter_by(subject_id=subject_id).order_by(Chapter.name).all()
    return render_template('user/chapters.html', subject=subject, chapters=chapters, Quiz=Quiz, Chapter=Chapter)

@user_bp.route('/chapters/<int:chapter_id>/quizzes')
@login_required
def chapter_quizzes(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    quizzes = Quiz.query.filter_by(chapter_id=chapter_id).order_by(Quiz.date_of_quiz).all()
    return render_template('user/quizzes.html', chapter=chapter, quizzes=quizzes)

@user_bp.route('/quizzes/<int:quiz_id>/attempt', methods=['GET', 'POST'])
@login_required
def attempt_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Check if quiz is available
    if quiz.date_of_quiz > date.today():
        flash('This quiz is not yet available.', 'warning')
        return redirect(url_for('user.user_dashboard'))
    
    # Check if user has already taken this quiz
    existing_score = Score.query.filter_by(quiz_id=quiz_id, user_id=current_user.id).first()
    if existing_score:
        flash('You have already taken this quiz. Check your results.', 'info')
        return redirect(url_for('user.results', score_id=existing_score.id))
    
    # Get all questions for this quiz
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    if not questions:
        flash('This quiz has no questions yet.', 'warning')
        return redirect(url_for('user.user_dashboard'))
    
    form = QuizAttemptForm()
    
    if form.validate_on_submit():
        total_questions = len(questions)
        total_scored = 0
        user_answers = {}
        
        for question in questions:
            question_id = str(question.id)
            user_answer = request.form.get(f'question_{question_id}')
            
            if user_answer and int(user_answer) == question.correct_option:
                total_scored += 1
                
            user_answers[question_id] = user_answer
        
        # Save score
        score = Score(
            quiz_id=quiz_id,
            user_id=current_user.id,
            total_scored=total_scored,
            total_questions=total_questions
        )
        score.set_answers(user_answers)
        db.session.add(score)
        db.session.commit()
        
        flash('Quiz submitted successfully!', 'success')
        return redirect(url_for('user.results', score_id=score.id))
    
    return render_template('user/attempt_quiz.html', quiz=quiz, questions=questions, form=form, Chapter=Chapter)

@user_bp.route('/results/<int:score_id>')
@login_required
def results(score_id):
    score = Score.query.get_or_404(score_id)
    
    # Ensure user can only see their own results
    if score.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    quiz = Quiz.query.get(score.quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()
    
    user_answers = score.get_answers()
    
    return render_template('user/results.html', score=score, quiz=quiz, questions=questions, user_answers=user_answers, Chapter=Chapter)

@user_bp.route('/scores')
@login_required
def user_scores():
    scores = Score.query.filter_by(user_id=current_user.id).order_by(Score.time_stamp.desc()).all()
    return render_template('user/scores.html', scores=scores, Quiz=Quiz)

# API routes for AJAX requests
@admin_bp.route('/api/subjects')
@login_required
@admin_required
def api_subjects():
    subjects = Subject.query.all()
    return jsonify([{'id': s.id, 'name': s.name} for s in subjects])

@admin_bp.route('/api/chapters/<int:subject_id>')
@login_required
@admin_required
def api_chapters(subject_id):
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    return jsonify([{'id': c.id, 'name': c.name} for c in chapters])

@admin_bp.route('/api/dashboard-stats')
@login_required
@admin_required
def api_dashboard_stats():
    stats = get_dashboard_stats()
    return jsonify({
        'total_users': stats['total_users'],
        'total_subjects': stats['total_subjects'],
        'total_quizzes': stats['total_quizzes'],
        'total_questions': stats['total_questions'],
        'quiz_stats': [
            {
                'name': quiz['quiz'].title,
                'avg_score': quiz['avg_score'],
                'attempts': quiz['attempts']
            }
            for quiz in stats['quiz_stats']
        ]
    })

@user_bp.route('/api/user-stats')
@login_required
def api_user_stats():
    stats = get_user_stats(current_user.id)
    return jsonify({
        'avg_percentage': stats['avg_percentage'],
        'completed_quizzes': stats['completed_quizzes'],
        'completion_rate': stats['completion_rate'],
        'subject_avg': stats['subject_avg']
    })