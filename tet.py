from datetime import datetime, timedelta

# Adding 60 seconds to the current time
current_time = datetime.now()
new_time = current_time + timedelta(seconds=60)

print("Current Time:", current_time)
print("New Time:", new_time)

from datetime import timedelta

delta = timedelta(days=100, hours=10, minutes=13)

print(delta)

from datetime import datetime


def convert_to_time(feet, inches):
    total_inches = feet * 12 + inches
    total_seconds = total_inches * 0.0254
    time_delta = datetime.fromtimestamp(total_seconds)
    return time_delta.strftime("%H:%M:%S")


# Example usage
feet = 5
inches = 8

converted_time = convert_to_time(feet, inches)
print("Converted Time:", converted_time)
