import re
import string
import requests
import json
import sendgrid
from random import choice
import uuid

import pandas as pd

from django.shortcuts import render
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse,JsonResponse,HttpResponseRedirect
from django.shortcuts import render,redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt,csrf_protect

from django.contrib.auth.models import User

from sendgrid.helpers import *
from sendgrid.helpers.mail import Mail, Content, Email

from main.models import UserProfile, UploadFile
from main import utils, email_body
# from sih.keyconfig import SENDGRID_API_KEY, FIREBASE_API_KEY, FCM_URL
from sih.keyconfig import *
from sih.settings import MEDIA_ROOT

chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
url = 'http://alertify.org'
USGS_GEODATA_URL = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson'


@csrf_exempt
def get_location(request):
    if request.method == 'GET':
        user_profiles = UserProfile.objects.all().exclude(lat=0, long=0).values('lat','long', 'is_safe', 'name')
        return JsonResponse({"location":list(user_profiles)})

@csrf_exempt
def get_food_location(request):
    if request.method == 'GET':
        user_profiles = UserProfile.objects.all().exclude(lat=0, long=0).values('lat','long', 'is_food_req', 'name')
        return JsonResponse({"location":list(user_profiles)})


def nill(request):
    return HttpResponse('nill')

@csrf_exempt
def register(request):

    if request.method == 'GET':
        return JsonResponse({'status':3, 'message':'The API where new users can register themselves on the app.'})

    if request.method=='POST':
        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})
        try:
            # see whether all fields passed in JSON or not
            data['name']
            data['email']
            data['phone']
            data['emergency_phone']
        except KeyError as missing_data:
            return JsonResponse({"message": "Missing the following field: {}".format(missing_data), 'status':2})

        try:
            int(data['phone'])
        except:
            #phone numbers should be an integer or string only of numbers
            return JsonResponse({'status':0,'message':'Please enter a valid Phone Number.'})

        try:
            int(data['emergency_phone'])
        except:
            #phone numbers should be an integer or string only of numbers
            return JsonResponse({'status':0,'message':'Please enter a valid Emergency Phone Number.'})

        if len(data['phone'])!=10:
            return JsonResponse({'status':0,'message':'Please enter a valid Phone Number.'})
        if len(data['emergency_phone'])!=10:
            return JsonResponse({'status':0,'message':'Please enter a valid Emergency Phone Number.'})

        email = data['email']
        if not re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email):
            return JsonResponse({'status':0, 'message':'Please enter a valid Email address.'})

        try:
            UserProfile.objects.get(email=email)
            return JsonResponse({'status':0, 'message':'This Email has already been registered. Try some other email.'})
        except:
            pass
        try:
            profile = UserProfile()
            name = ' '.join(str(data['name']).strip().split())
            profile.name = name
            profile.email = str(data['email'])
            profile.phone = int(data['phone'])
            profile.emergency_phone = int(data['emergency_phone'])
            profile.save()

            #verify email
            send_to = profile.email
            body = email_body.register()
            email_token = utils.generate_email_token(profile)
            body = body%(name, str(request.build_absolute_uri(reverse("main:nill"))) + 'email_confirm/' + email_token + '/')

            sg = sendgrid.SendGridAPIClient(apikey=SENDGRID_API_KEY)
            from_email = Email('register@alertify.com')
            to_email = Email(send_to)
            subject = "Email Confirmation for your account on Alertify app"
            content = Content('text/html', body)

            try:
                mail = Mail(from_email, subject, to_email, content)
                response = sg.client.mail.send.post(request_body=mail.get())
            except Exception:
                profile.delete()
                return JsonResponse({'message':'Error sending email. Please try again.', 'status':0})

            message = "Registration successful! A confirmation link has been sent to %s. Kindly click on it to verify your email address." %(send_to)
            return JsonResponse({'message':message, 'status':1})
        except Exception:
            return JsonResponse({'message': 'Registration failed due to unknown reasons.', 'status':0})


def mail_login_creds(user_profile):
    if not user_profile.user:
        username = user_profile.name.split(' ')[0] + str(user_profile.id)
        password = ''.join(choice(chars) for i in range(8))
        user = User.objects.create_user(username=username, password=password)
        user_profile.user = user
        user_profile.save()

        send_to = user_profile.email
        name = user_profile.name
        body = email_body.login_creds()
        body = body%(name, username, password)

        sg = sendgrid.SendGridAPIClient(apikey=SENDGRID_API_KEY)
        from_email = Email('register@alertify.com')
        to_email = Email(send_to)
        subject = "Login Credentials for your account on Alertify app"
        content = Content('text/html', body)

        try:
            mail = Mail(from_email, subject, to_email, content)
            response = sg.client.mail.send.post(request_body=mail.get())
            if response.status_code%100!=2:
                raise Exception
        except Exception:
            user_profile.user = None
            user_profile.save()
            user.delete()
            message = "Error in mailing your login credentials. Please try again."
            return message

        message = "Your login credentials have been sent to {0}.".format(send_to)
        return message


def check_user(request):
    try:
        user_id = str(request.META['HTTP_X_USER_ID'])
    except KeyError:
        return 0, JsonResponse({"message":"Header missing: X-USER-ID", "status":2})
    try:
        user_profile = UserProfile.objects.get(uuid=user_id)
        if not user_profile:
            raise Exception
    except Exception:
        return 0, JsonResponse({"message":"The given UserId doesnt correspond to any user."})
    return 1, user_id, user_profile



@csrf_exempt
def update_device_token(request):
    if request.method == 'POST':
        check = check_user(request)
        try:
            user_id, user_profile = check[1:]
        except ValueError:
            return check[1]
        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})
        try:
            device_token = data['device_token']
        except KeyError as missing_data:
            return JsonResponse({"message":"Field Missing: {0}".format(missing_data), "status":3})

        user_profile.device_token = device_token
        user_profile.save()

        return JsonResponse({"message":"Successfully Updated Device Token values.", "status":1})
    else:
        return JsonResponse({"message":"Requests other than POST is not Supported"})



@csrf_exempt
def auto_notify(request):
    if request.method == 'POST':
        # Note: Change to admin Auth
        # check = check_user(request)
        # try:
            # user_id, user_profile = check[1:]
        # except ValueError:
            # return check[1]
        # if not user_profile.is_da:
        #     return JsonResponse({"message":"You must be logged in as a DA to add events.", "status":0})

        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})
        # try:
        #     key = str(request.META['HTTP_GEO_UPDATE_KEY'])
        #     if key != GEO_UPDATE_KEY:
        #         return JsonResponse({"message":"Please authorize with GEO_UPDATE_KEY", "status":3})
        # except:
        #     return JsonResponse({"message":"Please authorize with GEO_UPDATE_KEY", "status":3})
        try:
            title = data['title']
            message = data['message']
            mag = data['mag']
            coords = data['coords']
        except KeyError as missing_data:
            return JsonResponse({"message":"Field Missing: {0}".format(missing_data), "status":3})
        try:
            lat = float(coords[0])
            long = float(coords[1])
            width = float(4)/2
            height = float(4)/2
        except:
            return JsonResponse({"message":'Invalid value for \'coords or box\'', "status":0})
        # Make list of user_profile.device_token and query all
        undone_users = []
        for u in UserProfile.objects.all():
            print(u)
            if (u.lat > lat - height and u.lat < lat + height) and (u.long > long - width and u.long < long + width):
                devToken = u.device_token
                try:
                    res = sendnotif(devToken, title, message)
                    print(res)
                    if res['failure'] == 1:
                        undone_users.append(u)
                except Exception:
                    undone_users.append(u)
        print(undone_users)
        return JsonResponse({ "undone_users":str(len(undone_users))})
            # Send sms to undone_users


# alternate method
def sendnotif(fcmdevicetoken, title, message):
    payload = {
     "data":{
        "title":title,
        "image":"https://firebase.google.com/images/social.png",
        "message":message,
      }, "to": fcmdevicetoken
    }
    headers={
      "content-type": "application/json",
      "authorization": "key={}".format(FIREBASE_API_KEY)
      }
    url = FCM_URL
    payload = json.dumps(payload)
    res = requests.post(url=url, headers=headers, data=payload)
    return res


def email_confirm(request,token):
    user_profile = utils.authenticate_email_token(token)
    if user_profile:
        if (not user_profile.email_verified) or (user_profile.email_verified and not user_profile.user):
            message = 'Your email has been verified.'
            mail_response = mail_login_creds(user_profile)
            message += mail_response
            context = {
                'error_heading': 'Email verified',
                'message': message,
                'url':url
            }
        else:
            # user had already verified his email
            context = {
                'error_heading': 'Email already verified',
                'message': 'Your email had been already verified. Please login into the app using your credentials.',
                'url':url
            }
    # if email verification token was wrong
    else:
        context = {
        'error_heading': "Invalid Token",
        'message': "Sorry!  Email couldn't be verified. Please try again.",
        'url':url
        }
    return render(request, 'main/message.html', context)

@csrf_exempt
def login_view(request):
    '''
    Login page
    '''

    # To do checks if user is authenticated

    if request.method == 'POST':
        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})
        try:
            username = data['username']
            password = data['password']
        except KeyError as missing_data:
            return JsonResponse({"message":"Field Missing: {0}".format(missing_data),"status":2})
        user = authenticate(username = username, password = password)

        if user is not None:
            login(request,user)
            # print(username,password)
            try:
                user_profile = UserProfile.objects.get(user = user)
            except:
                return JsonResponse({"message":"No Profile for the given user. ARE YOU LOGGED IN AS ADMIN?", "status":0})
            unique_id = str(user_profile.uuid)
            print(unique_id)
            return JsonResponse({"message":"Logged in Successfully!", "status":1, "user_id":unique_id})

        else:
            print('Invalid login creds')
            return JsonResponse({'message':'Invalid Login Credentials', 'status':0})
    elif request.method == 'GET':
        return JsonResponse({"message":"Supposed to be Login Page."})


@csrf_exempt
def update_food_location(request):
    if request.method == 'POST':
        check = check_user(request)
        try:
            user_id, user_profile = check[1:]
        except ValueError:
            return check[1]

        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})

        try:
            is_food_req = data['is_food_req']
        except KeyError as missing_data:
            return JsonResponse({"message":"Field Missing: {0}".format(missing_data), "status":3})

        # if (len(str(is_food_req)))>1:
        #     return JsonResponse({"message":"Invalid Value for is_food_req. Acceptable: 0 or 1", "status":0})

        if str(is_food_req) not in ["0","1"]:
            return JsonResponse({"message":"Invalid Value for is_food_req. Pass 0 or 1", "status":0})

        is_food_req = int(is_food_req)

        if is_food_req:
            user_profile.is_food_req = True
        if not is_food_req:
            user_profile.is_food_req = False
        user_profile.save()

        return JsonResponse({"message":"Updated status successfully!", "status":1})

    if request.method == "GET":
        return JsonResponse({"message":"API endpoint for updating food requirement status"})


@csrf_exempt
def update_location(request):
    if request.method=='POST':

        check = check_user(request)
        try:
            user_id, user_profile = check[1:]
        except ValueError:
            return check[1]

        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})

        try:
            data['long']
            data['lat']
        except KeyError as missing_data:
            return JsonResponse({"message":"Field Missing: {0}".format(missing_data), "status":3})

        try:
            latitude = float(data['lat'])
        except:
            return JsonResponse({"message":'Invalid value for \'lat\'', "status":0})
        try:
            longitude = float(data['long'])
        except:
            return JsonResponse({"message":'Invalid value for \'long\'', "status":0})

        if abs(latitude)>90:
            return JsonResponse({"message":"Latitude can only be in between -90 and 90.","status":0})
        if abs(longitude)>180:
            return JsonResponse({"message":"Longitude can only be in between -180 and 180.","status":0})

        user_profile.lat = latitude
        user_profile.long = longitude
        user_profile.save()

        return JsonResponse({"message":"Successfully Updated Latitude and Longitude values.", "status":1})

    if request.method == 'GET':
        return JsonResponse({"message":"API endpoint for updation of User Latitude and Longitude."})


@csrf_exempt
def update_safe_status(request):

    if request.method == 'POST':

        check = check_user(request)
        try:
            user_id, user_profile = check[1:]
        except ValueError:
            return check[1]

        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})

        try:
            is_safe = data['is_safe']
        except KeyError as missing_data:
            return JsonResponse({"message":"Field Missing: {0}".format(missing_data), "status":3})

        # if (len(str(is_safe)))>1:
        #     return JsonResponse({"message":"Invalid Value for is_safe. Acceptable: 0 or 1", "status":0})

        if str(is_safe) not in ["0","1"]:
            return JsonResponse({"message":"Invalid Value for is_safe. Pass 0 or 1", "status":0})

        is_safe = int(is_safe)

        if is_safe:
            user_profile.is_safe = True
        if not is_safe:
            user_profile.is_safe = False
        user_profile.save()

        return JsonResponse({"message":"Updated status successfully!", "status":1})

    if request.method == "GET":
        return JsonResponse({"message":"API endpoint for updating safety status"})

@csrf_exempt
def send_sms_request(list, message="URGENT: We have predicted high chances of a Tsunami striking in your area. Please be aware."):
    import json
    url = URL_SMS

    headers = {
        'authkey':AUTH_KEY_SMS,
        'Content-Type':'application/json'
    }
    data = {
        "sender": "ALERTF",
        "route": "4",
        "country": "91",
        "sms": [
            {
                "message": message ,
                "to": list
            }
        ]
    }
    print(data)
    response = requests.post(url = url, data = json.dumps(data), headers = headers)
    print(response.text)


@csrf_exempt
def send_sms(request):
    if request.method == 'POST':
        check = check_user(request)

        try:
            user_id, user_profile = check[1:]
        except ValueError:
            return check[1]

        if not user_profile.is_da:
            return JsonResponse({"message":"You must be logged in as a DA to add events.", "status":0})

        try:
            # just to decode JSON properly
            data = json.loads(request.body.decode('utf8').replace("'", '"'))
        except:
            return JsonResponse({"message": "Please check syntax of JSON data passed.", 'status':4})
        try:
            phone = data['phone']
            message = data['sms-body']
        except KeyError as missing_data:
            return JsonResponse({"message":"Field Missing: {0}".format(missing_data), "status":3})
        phone = str(phone)
        if len(phone)!=10 or not int(phone):
            return JsonResponse({"message":"Please enter a valid phone number."})

        phone = [str(phone)]
        send_sms_request(phone, message)
        return JsonResponse({"message":"SMS sent!"})
    else:
        return JsonResponse({"message":"Post SMS sending requests here,"})

@csrf_exempt
def upload_csv(request):
    if request.method == 'GET':
        return JsonResponse({"message":"Upload Excel/CSV files. "})
    # if not GET, then proceed
    FILE_FORMATS_SUPPORTED = ('.csv') #, '.xlsx', '.xls')
    try:
        file = request.FILES["csv_file"]
        if not file.name.endswith(FILE_FORMATS_SUPPORTED):
            return JsonResponse({"message":"File is not of CSV type."})

        if file.multiple_chunks():
            message = "Uploaded file is too big (%.2f MB)." % (csv_file.size/(1000*1000),)
            return JsonResponse({"message":message})

        upload_instance = UploadFile.objects.create(name=file.name, filer=file)
        send_sms_excel(upload_instance)
        message = "Uploaded Successfully!"
        context = {
            'error_heading': "File Uploaded Successfully!",
            'message': message,
            'url':url
        }
        return render(request, 'main/message.html', context)

    except Exception as e:
        print(e)
        message = "Error in Uploading File. Please try again."
        context = {
            'error_heading': "File not uploaded.",
            'message': message,
            'url':url
        }
        return render(request, 'main/message.html', context)

def send_sms_excel(file_instance):

    try:
        path = MEDIA_ROOT + '/' + file_instance.filer.name
        data = pd.read_csv(path)
    except:
        message = 'Error reading CSV.'
        return message
    phone_numbers = []

    for i in range(data.shape[0]):
        phone_numbers.append(str(data.loc[i][1]))

    result = phone_numbers
    send_sms_request(result)


# def excel_to_csv(excel_name):
#     import pandas as pd
#     try:
#         data_xls = pd.read_excel(excel_name, 'Sheet1', index_col=None)
#         csv_name = excel_name.strip('.')[0]+'.csv'
#         data_xls.to_csv(csv_name, encoding='utf-8')
#         return 1, data_xls
#     except Exception as e:
#         print(e)
#         return 0, str(e)

# def send_excel_sms(file_instance):
#     path = file_instance.filer.name
#     if path.endswith(('xls','xlsx')):
#         response = excel_to_csv(path)
#         if response:
#             csv = response[1]
#         else:
#             return JsonResponse({"message":"Sorry! Operation Failed."})


