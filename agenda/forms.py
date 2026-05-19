from datetime import datetime, timedelta

from django import forms
from django.forms import ModelForm
from django.utils import timezone

from .models import Training, BodyStats


class TrainingForm(ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date',
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}),
        label='Start time',
    )
    duration_minutes = forms.IntegerField(
        min_value=1, max_value=24 * 60,
        label='Duration (minutes)',
    )
    intensity = forms.ChoiceField(choices=Training.INTENSITY_CHOICES)

    class Meta:
        model = Training
        fields = ['title', 'description', 'intensity', 'crew']

    def __init__(self, *args, **kwargs):
        super(TrainingForm, self).__init__(*args, **kwargs)

        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'input'})


class BodyStatsForm(ModelForm):
    class Meta:
        model = BodyStats
        fields = ['weight', 'resting_heartrate', 'hrv', 'body_battery']
        labels = {
            'weight': 'Weight (kg)',
            'resting_heartrate': 'Resting heart rate (bpm)',
            'hrv': 'HRV (ms)',
            'body_battery': 'Body battery (0-100)',
        }

    def __init__(self, *args, **kwargs):
        super(BodyStatsForm, self).__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.update({'class': 'input'})

