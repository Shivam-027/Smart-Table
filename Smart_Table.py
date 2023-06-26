from flask import Flask, render_template, request, redirect, url_for
import RPi.GPIO as GPIO
import smbus2
import time
import csv
import threading 

app = Flask(__name__)
bus = smbus2.SMBus(1)

# Define LCD 
LCD_ADDR = 0x27
LCD_WIDTH = 16
LCD_CHR = 1
LCD_CMD = 0
LCD_LINE_1 = 0x80
LCD_LINE_2 = 0xC0
LCD_BACKLIGHT = 0x08
ENABLE = 0b00000100

# Initialize the LCD display
def lcd_init():
  lcd_byte(0x33, LCD_CMD) # Initialize
  lcd_byte(0x32, LCD_CMD) # Set to 4-bit mode
  lcd_byte(0x06, LCD_CMD) # Cursor move direction
  lcd_byte(0x0C, LCD_CMD) # Turn display on
  lcd_byte(0x28, LCD_CMD) # 2 line display
  lcd_byte(0x01, LCD_CMD) # Clear display
  time.sleep(0.0005)

# Send a byte to the LCD display
def lcd_byte(bits, mode):
  bits_high = mode | (bits & 0xF0) | LCD_BACKLIGHT
  bits_low = mode | ((bits<<4) & 0xF0) | LCD_BACKLIGHT
  bus.write_byte(LCD_ADDR, bits_high)
  lcd_toggle_enable(bits_high)
  bus.write_byte(LCD_ADDR, bits_low)
  lcd_toggle_enable(bits_low)

# Toggle the enable bit to send the data to the LCD display
def lcd_toggle_enable(bits):
  time.sleep(0.0005)
  bus.write_byte(LCD_ADDR, (bits | ENABLE))
  time.sleep(0.0005)
  bus.write_byte(LCD_ADDR, (bits & ~ENABLE))
  time.sleep(0.0005)

# Display the time and date on the LCD display
def lcd_display_time_date():
  lcd_byte(LCD_LINE_1, LCD_CMD)
  #lcd_byte(ord("Time: "), LCD_CHR)
  t = time.strftime("%H:%M:%S")
  t_chars = [ord(c) for c in t]
  for i in range(len(t_chars)):
    lcd_byte(t_chars[i], LCD_CHR)
  lcd_byte(LCD_LINE_2, LCD_CMD)
  #lcd_byte(ord("Date: "), LCD_CHR)
  d = time.strftime("%d/%m/%Y")
  d_chars = [ord(c) for c in d]
  for i in range(len(d_chars)):
    lcd_byte(d_chars[i], LCD_CHR)

# Update the clock every second
def update_clock():
    while True:
        lcd_display_time_date()
        time.sleep(1)
        
# Initialize the LCD display and display the time and date
lcd_init()
lcd_display_time_date()

# Set up GPIO pins
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(23, GPIO.OUT)
GPIO.setup(17, GPIO.OUT)
pir_pin = 4
light_pin = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup(pir_pin, GPIO.IN)
GPIO.setup(light_pin, GPIO.OUT)

# Set up alarm database
alarm_db = []
reminder_db = []

#read alarm
def read_alarm_db():
    with open('alarm_db.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return
        for row in reader:
            alarm_db.append({
                'id': int(row[0]),
                'time': row[1],
                'status': row[2]
            })

def write_alarm_db():
    with open('alarm_db.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'time', 'status'])
        for alarm in alarm_db:
            writer.writerow([alarm['id'], alarm['time'], alarm['status']])

#read reminder
def read_reminder_db():
    with open('reminder_db.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return
        for row in reader:
            reminder_db.append({
                'id': int(row[0]),
                'name': row[1],
                'description': row[2],
                'time': row[3],
                'status': row[4]
            })

def write_reminder_db():
    with open('reminder_db.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'name', 'description', 'time', 'status'])
        for reminder in reminder_db:
            writer.writerow([reminder['id'], reminder['name'], reminder['description'], reminder['time'], reminder['status']])

# Default motion detection status is off
motion_detection_on = False

# Global variable to control motion detection loop
motion_detection_loop_running = False

# Function to turn on/off the light
def toggle_lights(on):
    GPIO.output(light_pin, on)

# Function to check for motion and turn on/off light accordingly
def check_motion():
    global motion_detection_loop_running
    motion_detection_loop_running = True
    while motion_detection_loop_running:
        if GPIO.input(pir_pin) == GPIO.HIGH:
            print("Motion detected")
            toggle_lights(True)
            time.sleep(5)  # Keep light on for 5 seconds
        else:
            toggle_lights(False)
            time.sleep(0.1)  # Wait before checking again
    toggle_lights(False)  # Turn off light when motion detection is stopped

# Home page
@app.route('/')
def index():
    # Get the current state of the light
    light_state = GPIO.input(17)
    # Render template with current motion detection status
    return render_template("index.html", light_state=light_state)

@app.route('/motion',methods=["GET", "POST"])
def motion():
    global motion_detection_on, motion_detection_loop_running

    if request.method == "POST":
        # Toggle motion detection based on form input
        motion_detection_on = bool(request.form.get("motion_detection"))

        # Start or stop motion detection loop accordingly
        if motion_detection_on:
            motion_detection_thread = threading.Thread(target=check_motion)
            motion_detection_thread.start()
        else:
            motion_detection_loop_running = False

    # Render template with current motion detection status
    return render_template("motion.html",motion_detection_on=motion_detection_on)

@app.route('/alarm', methods=['POST'])
def index_a():
    return render_template('alarm.html', alarms=alarm_db)

@app.route('/reminder', methods=['POST'])
def index_r():
    return render_template('reminder.html', reminders=reminder_db)

@app.route('/back', methods=['POST'])
def back():
    # Get the current state of the light
    light_state = GPIO.input(17)
    return redirect(url_for('index'))

# Toggle light on or off
@app.route('/toggle', methods=['POST'])
def toggle_light():
    # Get the current state of the light
    light_state = GPIO.input(17)

    # Toggle the state of the light
    if light_state == GPIO.LOW:
        GPIO.output(17, GPIO.HIGH)
    else:
        GPIO.output(17, GPIO.LOW)

    # Redirect to the home page
    return index()

#alarm route
@app.route('/add_alarm', methods=['POST'])
def add_alarm():
    time = request.form['time']
    alarm_id = len(alarm_db) + 1
    alarm_db.append({
        'id': alarm_id,
        'time': time,
        'status': 'Inactive'
    })
    write_alarm_db()
    return render_template('alarm.html', alarms=alarm_db)

@app.route('/edit_alarm/<int:alarm_id>', methods=['GET', 'POST'])
def edit_alarm(alarm_id):
    if request.method == 'POST':
        time = request.form['time']
        for alarm in alarm_db:
            if alarm['id'] == alarm_id:
                alarm['time'] = time
                break
        write_alarm_db()
        return render_template('alarm.html', alarms=alarm_db)
    else:
        # handle GET request (render edit form)
        alarm = None
        for a in alarm_db:
            if a['id'] == alarm_id:
                alarm = a
                break
        if not alarm:
            return render_template('alarm.html', alarms=alarm_db)
        return render_template('edit_alarm.html', alarm=alarm)


@app.route('/delete_alarm/<int:alarm_id>')
def delete_alarm(alarm_id):
    for alarm in alarm_db:
        if alarm['id'] == alarm_id:
            alarm_db.remove(alarm)
            break
    write_alarm_db()
    return render_template('alarm.html', alarms=alarm_db)

@app.route('/activate_alarm/<int:alarm_id>')
def activate_alarm(alarm_id):
    for alarm in alarm_db:
        if alarm['id'] == alarm_id:
            alarm['status'] = 'Active'
            break
    write_alarm_db()
    return render_template('alarm.html', alarms=alarm_db)

@app.route('/deactivate_alarm/<int:alarm_id>')
def deactivate_alarm(alarm_id):
    for alarm in alarm_db:
        if alarm['id'] == alarm_id:
            alarm['status'] = 'Inactive'
            break
    write_alarm_db()
    return render_template('alarm.html', alarms=alarm_db)

#reminder route
@app.route('/add_reminder', methods=['POST'])
def add_reminder():
    name = request.form['name']
    description = request.form['description']
    time = request.form['time']
    reminder_id = len(reminder_db) + 1
    reminder_db.append({
        'id': reminder_id,
        'name': name,
        'description': description,
        'time': time,
        'status': 'Inactive'
    })
    write_reminder_db()
    return render_template('reminder.html', reminders=reminder_db)

@app.route('/reminder/<int:reminder_id>', methods=['GET', 'POST'])
def edit_reminder(reminder_id):
    if request.method == 'POST':
        time = request.form['time']
        for reminder in reminder_db:
            if reminder['id'] == reminder_id:
                reminder['time'] = time
                break
        write_reminder_db()
        return render_template('reminder.html', reminders=reminder_db)
    else:
        # handle GET request (render edit form)
        reminder = None
        for r in reminder_db:
            if r['id'] == reminder_id:
                reminder = r
                break
        if not reminder:
            return render_template('reminder.html', reminders=reminder_db)
        return render_template('edit_reminder.html', reminder=reminder)

@app.route('/delete_reminder/<int:reminder_id>')
def delete_reminder(reminder_id):
    for reminder in reminder_db:
        if reminder['id'] == reminder_id:
            reminder_db.remove(reminder)
            break
    write_reminder_db()
    return render_template('reminder.html', reminders=reminder_db)

@app.route('/activate_reminder/<int:reminder_id>')
def activate_reminder(reminder_id):
    for reminder in reminder_db:
        if reminder['id'] == reminder_id:
            reminder['status'] = 'Active'
            break
    write_reminder_db()
    return render_template('reminder.html', reminders=reminder_db)

@app.route('/deactivate_reminder/<int:reminder_id>')
def deactivate_reminder(reminder_id):
    for reminder in reminder_db:
        if reminder['id'] == reminder_id:
            reminder['status'] = 'Inactive'
            break
    write_reminder_db()
    return render_template('reminder.html', reminders=reminder_db)

def buzzer_on():
    GPIO.output(23, GPIO.HIGH)
    time.sleep(0.23)
    GPIO.output(23, GPIO.LOW)
    time.sleep(0.23)

def check_alarms():
    while True:
        current_time = time.strftime('%H:%M')
        for alarm in alarm_db:
            if alarm['time'] == current_time and alarm['status'] == 'Active':
                for i in range(10):
                    lcd_byte(LCD_LINE_2, LCD_CMD)
                    t = "ALARMING!"
                    t_chars = [ord(c) for c in t]
                    for i in range(len(t_chars)):
                      lcd_byte(t_chars[i], LCD_CHR)
                    buzzer_on()
        time.sleep(30) # check every 30 seconds

def check_reminders():
    while True:
        current_time = time.strftime('%H:%M')
        for reminder in reminder_db:
            if reminder['time'] == current_time and reminder['status'] == 'Active':
                for i in range(10):
                    lcd_byte(LCD_LINE_1, LCD_CMD)
                    t = "REMINDER!"
                    t_chars = [ord(c) for c in t]
                    for i in range(len(t_chars)):
                      lcd_byte(t_chars[i], LCD_CHR)
                    lcd_byte(LCD_LINE_2, LCD_CMD)
                    t = reminder['name']
                    t_chars = [ord(c) for c in t]
                    for i in range(len(t_chars)):
                      lcd_byte(t_chars[i], LCD_CHR)
                    buzzer_on()
                buzzer_on()
        time.sleep(30) # check every 30 seconds

# Start a separate thread to update the clock
clock_thread = threading.Thread(target=update_clock)
clock_thread.start()
    
if __name__ == '__main__':
    read_reminder_db()
    read_alarm_db()
    # Start a separate thread to check alarms
    import threading
    ## Start a separate thread to check alarm
    check_alarms_thread = threading.Thread(target=check_alarms)
    check_alarms_thread.start()
    ## Start a separate thread to check reminder
    check_reminders_thread = threading.Thread(target=check_reminders)
    check_reminders_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True)
