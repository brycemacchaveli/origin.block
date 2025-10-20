package utils

import (
	"fmt"
	"time"
)

// TimeFormat defines the standard time format used across the application
const TimeFormat = "2006-01-02T15:04:05Z07:00"

// FormatTime formats a time.Time to the standard string format
func FormatTime(t time.Time) string {
	return t.Format(TimeFormat)
}

// ParseTime parses a time string in the standard format
func ParseTime(timeStr string) (time.Time, error) {
	t, err := time.Parse(TimeFormat, timeStr)
	if err != nil {
		return time.Time{}, fmt.Errorf("failed to parse time %s: %v", timeStr, err)
	}
	return t, nil
}

// GetCurrentTimeString returns the current time as a formatted string
func GetCurrentTimeString() string {
	return FormatTime(time.Now())
}

// IsValidTimeRange checks if start time is before end time
func IsValidTimeRange(start, end time.Time) error {
	if start.After(end) {
		return fmt.Errorf("start time %s is after end time %s", FormatTime(start), FormatTime(end))
	}
	return nil
}

// IsWithinTimeRange checks if a time is within a given range
func IsWithinTimeRange(t, start, end time.Time) bool {
	return (t.Equal(start) || t.After(start)) && (t.Equal(end) || t.Before(end))
}

// AddBusinessDays adds business days to a date (excluding weekends)
func AddBusinessDays(start time.Time, days int) time.Time {
	current := start
	remaining := days
	
	for remaining > 0 {
		current = current.AddDate(0, 0, 1)
		// Skip weekends
		if current.Weekday() != time.Saturday && current.Weekday() != time.Sunday {
			remaining--
		}
	}
	
	return current
}

// CalculateAge calculates age in years from date of birth
func CalculateAge(dob time.Time) int {
	now := time.Now()
	age := now.Year() - dob.Year()
	
	// Adjust if birthday hasn't occurred this year
	if now.YearDay() < dob.YearDay() {
		age--
	}
	
	return age
}