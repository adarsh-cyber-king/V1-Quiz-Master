from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, SubmitField, BooleanField, SelectField, DateField, IntegerField, RadioField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, ValidationError
from datetime import date, datetime, timedelta
from models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    qualification = StringField('Qualification', validators=[Optional(), Length(max=120)])
    dob = DateField('Date of Birth', format='%Y-%m-%d', validators=[Optional()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password_confirm = PasswordField(
        'Confirm Password', validators=[DataRequired(), EqualTo('password')]
    )
    submit = SubmitField('Register')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already registered. Please use a different one.')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')
    
    def validate_dob(self, dob):
        if dob.data:
            today = date.today()
            age = today.year - dob.data.year - ((today.month, today.day) < (dob.data.month, dob.data.day))
            if age < 16:
                raise ValidationError('You must be at least 16 years old to register.')
            if age > 100:
                raise ValidationError('Please enter a valid date of birth.')

class SubjectForm(FlaskForm):
    name = StringField('Subject Name', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save')

class ChapterForm(FlaskForm):
    name = StringField('Chapter Name', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Description', validators=[Optional()])
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save')

class QuizForm(FlaskForm):
    title = StringField('Quiz Title', validators=[DataRequired(), Length(max=120)])
    chapter_id = SelectField('Chapter', coerce=int, validators=[DataRequired()])
    date_of_quiz = DateField('Date of Quiz', format='%Y-%m-%d', validators=[DataRequired()])
    time_duration = IntegerField('Duration (minutes)', validators=[DataRequired()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save')
    
    def validate_date_of_quiz(self, date_of_quiz):
        if date_of_quiz.data < date.today():
            raise ValidationError('Quiz date cannot be in the past.')
    
    def validate_time_duration(self, time_duration):
        if time_duration.data < 1:
            raise ValidationError('Quiz duration must be at least 1 minute.')
        if time_duration.data > 180:
            raise ValidationError('Quiz duration cannot exceed 3 hours (180 minutes).')

class QuestionForm(FlaskForm):
    question_text = TextAreaField('Question', validators=[DataRequired()])
    option_1 = StringField('Option 1', validators=[DataRequired(), Length(max=256)])
    option_2 = StringField('Option 2', validators=[DataRequired(), Length(max=256)])
    option_3 = StringField('Option 3', validators=[DataRequired(), Length(max=256)])
    option_4 = StringField('Option 4', validators=[DataRequired(), Length(max=256)])
    correct_option = RadioField('Correct Option', 
                              choices=[(1, 'Option 1'), (2, 'Option 2'), (3, 'Option 3'), (4, 'Option 4')],
                              coerce=int,
                              validators=[DataRequired()])
    submit = SubmitField('Save')

class QuizAttemptForm(FlaskForm):
    submit = SubmitField('Submit Quiz')

class SearchForm(FlaskForm):
    query = StringField('Search', validators=[DataRequired()])
    submit = SubmitField('Search')