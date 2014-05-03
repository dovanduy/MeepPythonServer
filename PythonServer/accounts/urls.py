from django.conf.urls import url, patterns
from django.contrib.auth.decorators import login_required

urlpatterns = patterns("accounts.views",
                        url(r"^create_user", "createUser"),
                        url(r"^update_user", "updateUser"),
                        url(r"^update_setting_field", "updateSettingField"),
                        url(r"^search_by_email", "searchByEmail"),
                        url(r"^add_friend", "addFriend"),
                        url(r"^create_group", "createGroup"),
                        url(r"^update_group/(\d+)", "updateGroup"),
                        url(r"^group_add_users/(\d+)", "addUsersToGroup"),
                        )

urlpatterns += patterns("accounts.api",
                        # manual refreshing/updating of campaign backend data
                        url(r"^register$", "registerUser"),
                        url(r"^login$", "login"),
                        url(r"^update$", "updateAccountProfileField"),
                        url(r"^settings/update$", "updateAccountSettingField"),
                        url(r"^settings/get$", "getAccountSettings"),
                        url(r"^search/email", "searchUsersByEmail"),
                        url(r"^friends/new", "addFriend"),
                        url(r"^friends/list/(\d+)", "getFriends"),
                        url(r"^syncFacebookFriends$", "syncFacebookFriends"),
                        url(r"^getAccessToken$", "getAccessToken"),
                        url(r'^venmoTransaction$', 'venmoTransaction'),
                        url(r'^venmoGetUserFriendList$', 'venmoGetUserFriendList'),
                        url(r'^venmoGetUserInfo$', 'venmoGetUserInfo'),
                        url(r'^venmoGetAccessToken$', 'venmoGetAccessToken'),
                        url(r'^venmo_connect$', 'venmoConnect'),
                        url(r'^facebook_connect$', 'facebookConnect'),
                        url(r"^group/new", "createGroup"),
                        url(r"^group/list/(\d+)", "getGroups"),
                        url(r"^group/(\d+)/members/add", "addUsersToGroup"),
                        url(r"^group/(\d+)/members/remove", "removeUsersFromGroup"),
                        url(r"^group/(\d+)/update", "updateGroup"),
                        url(r"^group/(\d+)", "getGroup"),
                        )