import json
import logging
import ast
import re
import urllib2
import urllib
import urlparse
import oauth2 as oauth
import httplib2
import datetime
from celery import task
from facepy import GraphAPI
from PythonServer.settings import RETURN_LIST_SIZE
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import loader, Context, RequestContext
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import model_to_dict
from ios_notifications.models import APNService, Notification, Device
from accounts.models import Account, AccountLink, Group, AccountSetting, AccountSettings, FacebookProfile, VenmoProfile
from events.models import Event, InvitedFriend
from notifications.api import registerDevice, createNotification, sendNotification, addNotificationToRedis
from django.contrib.auth.hashers import make_password
from django.views.decorators.csrf import csrf_exempt
from forms import RegisterForm
from rediscli import r as R

logger = logging.getLogger("django.request")

ACCESS_TOKEN_URL        = "https://graph.facebook.com/oauth/access_token"
REQUEST_TOKEN_URL       = "https://www.facebook.com/dialog/oauth"
CHECK_AUTH              = "https://graph.facebook.com/me"
GRAPH_URL               = "https://graph.facebook.com/"
VIEW_POSTS_URL          = "https://graph.facebook.com/search?access_token="
FB_GET_URL              = "https://graph.facebook.com/?id="
ANOTHER_FB_URL          = "https://api.facebook.com/method/fql.query?query="
ALT_QUERY_URL           = "https://api-read.facebook.com/restserver.php?method=fql.query&query="

APP_ID					= "1425290317728330"
APP_SECRET				= "6af15c8c3a845b550379e011fc4f7a83"

VENMO_ACCESS_TOKEN 		= "LGS5yhZuaQh4gur9Qk2g9ntUCHgsQ9ev"
VENMO_SECRET			= "rB5ffYe6LZUbWvjpADugLMUCL8gZPYst"
VENMO_ID				= "1692"
VENMO_ANDROID_RETURN_URL= "venmo1692://"

@task
def pushToNOSQLHash(key, push_item):
	r = R.r
	r.hmset(key, push_item)


@task
def pushToNOSQLSet(key, push_item, delete_item, score):
	r = R.r
	r.zadd(key, push_item, score)
	if delete_item:
		r.zrem(key, delete_item)


def venmoTransaction(request):
	rtn_dict = {"success": False, "msg": ""}
	venmo_user_to_charge = {}
	charged_id = 2
	venmo_user_to_charge['user_id'] = "145434160922624933"
	venmo_user_to_charge['email'] = "venmo@venmo.com"
	venmo_user_to_charge['phone'] = 15555555555
	venmo_user_to_charge['amount'] = .10
	venmo_user_to_charge['note'] = "Test payment"
	try:
		account = Account.objects.get(user=request.user)
		#charged_account = Account.objects.get(pk=charged_id)
		venmo_account = VenmoProfile.objects.get(user=account)
		#charged_venmo_account = VenmoProfile.objects.get(user=charged_account)
		access_token = venmo_account.access_token
		venmo_user_to_charge['access_token'] = access_token

		#url = "https://api.venmo.com/v1/payments"
		url = "https://sandbox-api.venmo.com/v1/payments"
		data = {}
		try:
			data = urllib.urlencode(venmo_user_to_charge)
			conn = urllib2.urlopen(url, data)
			try:
				response = json.loads(conn.read())
				'''
				venmo_transaction = VenmoTransaction(charger=venmo_account, charged=charged_venmo_account)
				venmo_transaction.payment_id = response['data']['payment']['id']
				venmo_transaction.note = response['data']['payment']['note']
				venmo_transaction.amount = response['data']['payment']['amount']
				venmo_transaction.date_completed = response['data']['payment']['date_completed']
				venmo_transaction.date_created = response['data']['payment']['date_created']
				venmo_transaction.save()
				'''
				rtn_dict['msg'] = 'Successfully got venmo user info'
				rtn_dict['success'] = True
			finally:
				conn.close()
		except urllib2.HTTPError as error:
			print 'Error pulling info from venmo api: {0}'.format(error)
			rtn_dict['msg'] = 'Error pulling info from venmo api: {0}'.format(error)

	except Exception as e:
		print 'unable to get venmo user info {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


def venmoGetUserInfo(request):
	rtn_dict = {"success": False, "msg": ""}
	try:
		account = Account.objects.get(user=request.user)
		venmo_account = VenmoProfile.objects.get(user=account)
		access_token = venmo_account.access_token
		url = "https://api.venmo.com/v1/me?access_token={0}".format(access_token)
		try:
			conn = urllib2.urlopen(url)

			try:
				response = json.loads(conn.read())
				venmo_account.venmo_id = response['data']['user']['id']
				venmo_account.first_name = response['data']['user']['first_name']
				venmo_account.last_name = response['data']['user']['last_name']
				venmo_account.email = response['data']['user']['email']
				venmo_account.save()
				rtn_dict['msg'] = 'Successfully got venmo user info'
				rtn_dict['success'] = True
			finally:
				conn.close()
		except urllib2.HTTPError as error:
			print 'Error pulling info from venmo api: {0}'.format(error)
			rtn_dict['msg'] = 'Error pulling info from venmo api: {0}'.format(error)

	except Exception as e:
		print 'unable to get venmo user info {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


def venmoGetUserFriendList(request):
	rtn_dict = {"success": False, "msg": ""}
	try:
		account = Account.objects.get(user=request.user)
		venmo_account = VenmoProfile.objects.get(user=account)
		access_token = venmo_account.access_token
		friend_list_url = "https://api.venmo.com/v1/users/{0}/friends?access_token={1}".format(venmo_account.venmo_id, access_token)
		try:
			conn = urllib2.urlopen(friend_list_url)
			try:
				response = json.loads(conn.read())
				print 'response'
				print response
				rtn_dict['msg'] = 'Successfully got venmo user info'
				rtn_dict['success'] = True
			finally:
				conn.close()
		except urllib2.HTTPError as error:
			print 'Error pulling info from venmo api: {0}'.format(error)
			rtn_dict['msg'] = 'Error pulling info from venmo api: {0}'.format(error)

	except Exception as e:
		print 'unable to get venmo user info {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


def venmoGetAccessToken(request):
	rtn_dict = {"success": False, "msg": ""}
	access_token = request.GET.get('access_token', '')

	try:
		account = Account.objects.get(user=request.user)
		try:
			venmo_profile = VenmoProfile.objects.get(user=account)
			venmo_profile.access_token = access_token
			venmo_profile.save()
		except:
			venmo_profile = VenmoProfile(user=account)
			venmo_profile.access_token = access_token
			venmo_profile.save()
	except Exception as e:
		print 'No user account can be found: {0}'.format(e)

	rtn_dict['access_token'] = access_token

	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


def venmoConnect(request):
	#url = "https://api.venmo.com/v1/oauth/authorize?client_id={0}&scope=make_payments%20access_profile%20access_friends%20access_email".format(VENMO_ID)
	url = "https://sandbox-api.venmo.com/v1/oauth/authorize?client_id={0}&scope=make_payments%20access_profile%20access_friends%20access_email".format(VENMO_ID)
	return HttpResponseRedirect(url)


def syncFacebookFriends(request):
	rtn_dict = {"success": False, "msg": "", "fb_pf": False}
	facebook = None
	if not request.user.id:
		user_id = request.POST['user']
	else:
		user_id = request.user.id
	# Try to get a pre-existing Facebook Profile for the signed in user
	try:
		account = Account.objects.get(user__id=user_id)
		facebook = FacebookProfile.objects.get(user=account)
		rtn_dict['fb_pf'] = True
	except Exception as e:
		print 'User facebook profile does not exist for user {0}: {1}'.format(user_id, e)
		rtn_dict['msg'] = 'User facebook profile does not exist for user {0}: {1}'.format(user_id, e)
		#should be implied that user needs to sign in through fb and allow permissions before you can sync friends

	if facebook:
		try:
			redirect_uri = 'http://' + request.META['HTTP_HOST'] + '/acct/syncFacebookFriends'
			graph = GraphAPI()
			# getting user friend list
			path = str(facebook.facebook_id) + '/friends'
			content_dict = graph.get(
				path=path,
				redirect_uri=redirect_uri,
				access_token=facebook.access_token
			)
			# getting list from dict of user friends
			friends = content_dict['data']
			for friend_dict in friends:
				facebook_id = friend_dict['id']
				try:
					#find friend with this fb id in our db
					friend_account = Account.objects.get(facebook_id=facebook_id)
					try:
						account_link = AccountLink(account_user=account,friend=friend_account)
						account_link.save()
						redis_key = 'account.{0}.friends.set'.format(account.id)
						friend_dict = json.dumps({'id': friend_account.id, 'pf_pic': friend_account.profile_pic, 'name': friend_account.display_name})
						pushToNOSQLSet(redis_key, friend_dict, False,0)
					except:
						logger.info('Tried creating an AccountLink that already exists')
						print 'Tried creating an AccountLink that already exists'
					try:
						account_link = AccountLink(account_user=friend_account,friend=account)
						account_link.save()
						redis_key = 'account.{0}.friends.set'.format(friend_account.id)
						friend_dict = json.dumps({'id': account.id, 'pf_pic': account.profile_pic, 'name': account.display_name})
						pushToNOSQLSet(redis_key, friend_dict, False,0)
					except:
						logger.info('Tried creating an AccountLink that already exists')
						print 'Tried creating an AccountLink that already exists'
				except:
					pass

			rtn_dict['success'] = True
			rtn_dict['msg'] = 'Successfully synced users facebook friends who have Meep accounts'
		except Exception as e:
			print 'Error with facebook graph api for user {0}: {1}'.format(facebook.facebook_id, e)

	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


def getAccessToken(request):
	rtn_dict = {"success": False, "msg": ""}
	code = request.GET.get('code')
	consumer = oauth.Consumer(key=APP_ID, secret=APP_SECRET)
	client = oauth.Client(consumer)
	redirect_uri = 'http://' + request.META['HTTP_HOST'] + '/acct/getAccessToken'
	try:
		graph = GraphAPI()
		# getting access code
		content = graph.get(
			path='oauth/access_token',
			client_id=APP_ID,
			client_secret=APP_SECRET,
			redirect_uri=redirect_uri,
			code=code
		)
		access_token = dict(urlparse.parse_qsl(content))['access_token']
		request_url = CHECK_AUTH + '?access_token=%s' % access_token

		#getting user data dict
		content_dict = graph.get(
			path='me',
			redirect_uri=redirect_uri,
			access_token=access_token
		)

		userid = content_dict['id']
		if not request.user.id:
			user_id = request.POST['user']
		else:
			user_id = request.user.id
		account = Account.objects.get(user__id=user_id)
		try:
			myprofile = FacebookProfile.objects.get(user=account)
			myprofile.active = True
			myprofile.update_token(access_token)
			# COULD POTENTIALLY UPDATE ACCOUNT WITH NEW FB DATA HERE TOO
		except:
 			myprofile = FacebookProfile(user=account, facebook_id=userid, image_url=(GRAPH_URL + content_dict['username'] + '/picture'), access_token=access_token)
			myprofile.get_remote_image()
			myprofile.active = True
			myprofile.save()
			account.facebook_id = str(userid)
			account.first_name = content_dict['first_name']
			account.last_name = content_dict['last_name']
			account.email = content_dict['email']
			account.profile_pic = myprofile.profilePicture
			try:
				account.gender = content_dict['gender']
			except:
				pass
			try:
				birthday_str = content_dict['birthday']
				birthday = datetime.datetime.strptime(birthday_str, "%m/%d/%Y").date()
				account.birthday = birthday
			except Exception as e:
				print 'error saving birthday: {0}'.format(e)
			try:
				account.home_town = content_dict['hometown']['name']
			except:
				pass
			account.save()

		rtn_dict['success'] = True
		rtn_dict['msg'] = 'successfully got access token'
	except Exception as e:
		print 'error authorizing user: {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


def facebookConnect(request):
	rtn_dict = {"success": False, "msg": ""}
	try:
		if not request.user.id:
			user_id = request.POST['user']
		else:
			user_id = request.user.id
		account = Account.objects.get(user__id=user_id)
		facebook = FacebookProfile.objects.get(user=account)
		facebook.active = True
		facebook.save()
		rtn_dict['success'] = True
		rtn_dict['msg'] = 'Successfully connected to facebook'
		return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")
	except Exception, e:
		print 'Error getting user facebook profile: {0}'.format(e)
	callback_url = 'http://localtest.channelfactory.com:8000/acct/getAccessToken'
	return HttpResponseRedirect(REQUEST_TOKEN_URL + '?client_id=%s&redirect_uri=%s&scope=%s' % (APP_ID, urllib.quote_plus(callback_url),'email,read_friendlists, user_photos, user_birthday, user_events, user_groups'))


@csrf_exempt
def registerUser(request):
	rtn_dict = {'success': False, "msg": ""}
	if request.method == 'POST':
		try:
			new_user = User(username=request.POST.get("username"))
			new_user.is_active = True
			new_user.password = make_password(request.POST.get('password1'))
			new_user.email = request.POST.get('email')
			new_user.save()
			user = authenticate(username=request.POST.get("username"), password=request.POST.get("password1"))
			auth_login(request, user)
			account = Account(user=user)
			account.email = user.email
			account.user_name = user.username
			account.save()
			r = R.r
			#PUSH NOTIFICATIONS
			token = request.POST.get('device_token', None)
			if token is not None:
				try:
					# Strip out any special characters that may be in the token
					token = re.sub('<|>|\s', '', token)
					registerDevice(user, token)
					device_token_key = 'account.{0}.device_tokens.hash'.format(account.id)
					token_dict = {str(token): True}
					r.hmset(device_token_key, token_dict)
				except Exception as e:
					print 'Error allowing push notifications {0}'.format(e)
			
			user_key = 'account.{0}.hash'.format(account.id)
			r.hmset(user_key, model_to_dict(account))


			rtn_dict['success'] = True
			rtn_dict['msg'] = 'Successfully registered new user'
			rtn_dict['user'] = new_user.id
			rtn_dict['account'] = account.id
		except Exception as e:
			print 'Error registering new user: {0}'.format(e)
			logger.info('Error registering new user: {0}'.format(e))
			rtn_dict['msg'] = 'Error registering new user: {0}'.format(e)

	else:
		rtn_dict['msg'] = 'Not POST'

	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


@csrf_exempt
def login(request):
	login_failed = False
	if request.method == "POST":
 		username = request.POST.get('username')
		password = request.POST.get('password')
		user = authenticate(username=username, password=password)
		if user is not None:
			if user.is_active:
				auth_login(request, user)
			else:
				return HttpResponseForbidden(\
					content='Your account is not active.')
		else:
			login_failed = True

	if request.user.is_authenticated():
		status = 200
	else:
		status = 401

	response = render_to_response('accounts/login.html', {},
                                  context_instance=RequestContext(request))
	response.status_code = status
	if login_failed:
		response['Auth-Response'] = 'Login failed'

	return response


#login_required
@csrf_exempt
def updateUser(request):
    rtn_dict = {'success': False, "msg": ""}

    if request.method == 'POST':
		try:
			if not request.user.id:
				user_id = request.POST['user']
			else:
				user_id = request.user.id
			account = Account.objects.get(user__id=user_id)
			r = R.r 
			redis_key = 'account.{0}.hash'.format(account.id)
			redis_account = r.hgetall(redis_key)

			try:
				account.user_name = request.POST['username']
			except:
				pass
			try:
				account.first_name = request.POST['first_name']
			except:
				pass
			try:
				account.last_name = request.POST['last_name']
			except:
				pass
			try:
				account.phone_number = request.POST['phone_number']
			except:
				pass
			try:
				account.profile_pic = request.POST['profile_pic']
			except:
				pass
			try:
				account.email = request.POST['email']
			except:
				pass
			try:
				account.gender = request.POST['gender']
			except:
				pass
			try:
				account.birthday = request.POST['birthday']
			except:
				pass
			try:
				account.home_town = request.POST['home_town']
			except:
				pass
			try:
				account.is_active = request.POST['is_active']
			except:
				pass
			account.save()

			pushToNOSQLHash(redis_key, model_to_dict(account))

			rtn_dict['success'] = True
			rtn_dict['msg'] = 'successfully updated user {0}'.format(account)
		except Exception as e:
			logger.info('Error registering new user: {0}'.format(e))
			rtn_dict['msg'] = 'Error registering new user: {0}'.format(e)
    return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


#login_required
@csrf_exempt
def searchUsersByEmail(request):
	rtn_dict = {'success': False, "msg": "", "users": []}
	if request.method == 'POST':
		try:
			r = R.r

			searched_users = []
			search_field = request.POST['search_field']
			users = Account.objects.filter(email__startswith=search_field, is_active=True)
			for user in users:
				searched_users.append(model_to_dict(user))
			rtn_dict['users'] = searched_users

		except Exception as e:
			logger.info('Error searching for useres: {0}'.format(e))
			rtn_dict['msg'] = 'Error searching for useres: {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


#login_required
@csrf_exempt
def addFriend(request):
	rtn_dict = {'success': False, "msg": ""}
	if request.method == 'POST':
		try:
			if not request.user.id:
				user_id = request.POST['user']
			else:
				user_id = request.user.id
			account = Account.objects.get(user__id=user_id, is_active=True)
			friend = Account.objects.get(pk=request.POST['friend_id'], is_active=True)
			if account.id != friend.id:
				link = AccountLink(account_user=account, friend=friend)
				link.save()

				second_link = AccountLink(account_user=friend, friend=account)
				second_link.save(create_notification=True)

				redis_key = 'account.{0}.friends.set'.format(account.id)
				friend_dict = json.dumps({'id': friend.id, 'pf_pic': friend.profile_pic, 'name': friend.display_name})
				pushToNOSQLSet(redis_key, friend_dict, False,0)

				redis_key = 'account.{0}.friends.set'.format(friend.id)
				friend_dict = json.dumps({'id': account.id, 'pf_pic': account.profile_pic, 'name': account.display_name})
				pushToNOSQLSet(redis_key, friend_dict, False,0)

				rtn_dict['success'] = True
				rtn_dict['msg'] = 'successfully added friend {0}'.format(friend.id)
			else:
				print 'Error adding friend: User and friend are the same person'
				logger.info('Error adding friend: User and friend are the same person')
				rtn_dict['msg'] = 'Error adding friend: User and friend are the same person'
		except Exception as e:
			print 'Error searching for useres: {0}'.format(e)
			logger.info('Error searching for useres: {0}'.format(e))
			rtn_dict['msg'] = 'Error adding friend: {0}'.format(e)
	else:
		rtn_dict['msg'] = 'Not POST'
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


#login_required
def getFriends(request, account_id):
	rtn_dict = {'success': False, "msg": "", "friends": []}

	try:
		friends_range_start = int(request.GET.get('range_start', 0))
		r = R.r
		redis_key = 'account.{0}.friends.set'.format(account_id)
		friends_list = r.zrange(redis_key, friends_range_start, friends_range_start + RETURN_LIST_SIZE)
		if not friends_list:
			friends_list = []
			account = Account.objects.get(pk=account_id)
			friend_links = AccountLink.objects.select_related('friend').filter(account_user=account).order_by('invited_count')
			for link in friend_links:
				if link.friend.is_active:
					friend_dict = {'pf_pic': None, 'id':None, 'name': None}
					friend_dict['pf_pic'] = link.friend.profile_pic
					friend_dict['id'] = link.friend.id
					friend_dict['name'] = link.friend.user_name
					friends_list.append(json.dumps(friend_dict))
			rtn_dict['success'] = True
			rtn_dict['msg'] = 'successfully retrieved friend list'
			rtn_dict['friends'] = friends_list

		rtn_dict['friends'] = friends_list
		rtn_dict['success'] = True
		rtn_dict['msg'] = 'successfully retrieved friend list'
	except Exception as e:
		logger.info('Error getting friend list: {0}'.format(e))
		rtn_dict['msg'] = 'Error getting friend list: {0}'.format(e)

	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


#login_required
@csrf_exempt
def createGroup(request):
	rtn_dict = {'success': False, "msg": ""}
	if request.method == 'POST':
		try:
			if not request.user.id:
				user_id = request.POST['user']
			else:
				user_id = request.user.id
			account = Account.objects.get(user__id=user_id)
			group = Group(group_creator=account)
			group.name = request.POST['name']
			group.save()
			members = ast.literal_eval(request.POST['members'])
			for member_id in members:
				friend = Account.objects.get(pk=member_id, is_active=True)
				group.members.add(friend)
			group.members.add(account)
			r = R.r
			r_group_key = 'group.{0}.hash'.format(group.id)
			pushToNOSQLHash(r_group_key, model_to_dict(group))

			message = "You have been added to group {0} by {1}".format(group.name, group.group_creator.user_name)
			custom_payload = {'creator_name': group.group_creator.user_name,
								'creator_id': group.group_creator.id,
								'group_name': group.name,
								'group_id': group.id}
			custom_payload = json.dumps(custom_payload)
			notification = createNotification(message, custom_payload)
			#add group to groups for members
			for member in group.members.all():
				#creating notification to send to group members
				recipient = member.user
				notification.recipients.add(recipient)
				addNotificationToRedis(notification, member.id)
				r_groups_key = 'account.{0}.groups.set'.format(member.id)
				pushToNOSQLSet(r_groups_key, group.id, False, 0)
		except Exception as e:
			print 'Error creating group: {0}'.format(e)
			logger.info('Error creating group: {0}'.format(e))
			rtn_dict['msg'] = 'Error creating group: {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


#@login_required
def getGroup(request, group_id):
	rtn_dict = {'success': False, "msg": "", "group": ""}
	try:
		r = R.r
		r_group_key = 'group.{0}.hash'.format(group_id)
		group = r.hgetall(r_group_key)
		if not group:
			if not request.user.id:
				user_id = request.POST['user']
			else:
				user_id = request.user.id
			account = Account.objects.get(user__id=user_id, is_active=True)
			group = Group.objects.get(pk=group_id)
			group = model_to_dict(group)
		rtn_dict['group'] = group
		rtn_dict['success'] = True
		rtn_dict['msg'] = 'successfully retrieved group {0}'.format(group_id)
	except Exception as e:
		logger.info('Error retrieving group: {0}'.format(e))
		rtn_dict['msg'] = 'Error retrieving group: {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


#@login_required
def getGroups(request):
	rtn_dict = {'success': False, "msg": "", "groups": []}
	try:
		groups_range_start = int(request.GET.get('range_start', 0))
		group_list = []
		if not request.user.id:
			user_id = request.POST['user']
		else:
			user_id = request.user.id
		account = Account.objects.get(user__id=user_id)
		r = R.r
		r_groups_key = 'account.{0}.groups.set'.format(account.id)
		r_groups = r.zrange(r_groups_key, groups_range_start, groups_range_start + RETURN_LIST_SIZE)

		if not r_groups:
			account = Account.objects.get(user=request.user, is_active=True)
			groups = Group.objects.filter(members__id=account.id)
			for group in groups:
				group_list.append(model_to_dict(group))
		else:
			for group_id in r_groups:
				r_group_key = 'group.{0}.hash'.format(group_id)
				group_list.append(json.dumps(r.hgetall(r_group_key)))

		rtn_dict['groups'] = group_list
		rtn_dict['success'] = True
		rtn_dict['msg'] = 'successfully retrieved groups'
	except Exception as e:
		logger.info('Error retrieving groups: {0}'.format(e))
		rtn_dict['msg'] = 'Error retrieving groups: {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


#@login_required
@csrf_exempt
def addUsersToGroup(request, group_id):
	rtn_dict = {'success': False, "msg": ""}
	if request.method == 'POST':
		try:
			if not request.user.id:
				user_id = request.POST['user']
			else:
				user_id = request.user.id
			creator = Account.objects.get(user__id=user_id, is_active=True)
			group = Group.objects.get(pk=group_id)

			members_to_add = ast.literal_eval(json.loads(request.POST['new_members']))

			for member_id in members_to_add:
				new_member = Account.objects.get(pk=member_id)
				link = AccountLink.objects.get(account_user=creator, friend=new_member)
				group.members.add(new_member)

			r = R.r
			r_group_key = 'group.{0}.hash'.format(group.id)
			pushToNOSQLHash(r_group_key, model_to_dict(group))

			#add group to groups for members
			for member in group.members.all():
				r_groups_key = 'account.{0}.groups.set'.format(member.id)
				pushToNOSQLSet(r_groups_key, group.id, False, 0)

			rtn_dict['success'] = True
			rtn_dict['msg'] = 'successfully added users to group {0}'.format(group_id)
		except Exception as e:
			print 'Error adding users to group: {0}'.format(e)
			logger.info('Error adding users to group: {0}'.format(e))
			rtn_dict['msg'] = 'Error adding users to group: {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


@csrf_exempt
def removeUsersFromGroup(request, group_id):
	rtn_dict = {'success': False, "msg": ""}
	if request.method == 'POST':
		try:
			if not request.user.id:
				user_id = request.POST['user']
			else:
				user_id = request.user.id
			creator = Account.objects.get(user__id=user_id, is_active=True)
			group = Group.objects.get(pk=group_id, group_creator=creator)
			members_to_remove = request.POST['members_to_remove']
			for member_id in members_to_remove:
				member_to_remove = Account.objects.get(pk=member_id)
				group.members.remove(new_member)
			'''
				TODO: Write redis code for removing users from group
			'''
			rtn_dict['success'] = True
			rtn_dict['msg'] = 'successfully removed users from group {0}'.format(group_id)
		except Exception as e:
			logger.info('Error removing users from group: {0}'.format(e))
			rtn_dict['msg'] = 'Error removing users from group: {0}'.format(e)
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


@csrf_exempt
def updateGroup(request, group_id):
	rtn_dict = {'success': False, "msg": ""}
	if request.method == 'POST':
		try:
			if not request.user.id:
				user_id = request.POST['user']
			else:
				user_id = request.user.id
			creator = Account.objects.get(user__id=user_id, is_active=True)
			group = Group.objects.get(pk=group_id, group_creator=creator)
			group.name = request.POST['new_name']
			group.save()
			r = R.r
			r_group_key = 'group.{0}.hash'.format(group_id)
			group['name'] = request.POST['new_name']
			pushToNOSQLHash(r_group_key, model_to_dict(group))
			rtn_dict['success'] = True
			rtn_dict['msg'] = 'successfully edited group {0}'.format(group_id)
		except Exception as e:
			logger.info('Error retrieving groups: {0}'.format(e))
			rtn_dict['msg'] = 'Error retrieving groups: {0}'.format(e)
	else:
		rtn_dict['msg'] = 'Not POST'
	return HttpResponse(json.dumps(rtn_dict, cls=DjangoJSONEncoder), content_type="application/json")


def updateAccount(request):
	pass
