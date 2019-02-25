from django.conf.urls import url
from django.contrib.auth.views import logout
from main import views
app_name = 'main'

urlpatterns = [
    url(r'^$',views.nill,name='nill'),
	url(r'^register/?',views.register,name='register'),
	url(r'^email_confirm/(?P<token>\w+)/?',views.email_confirm,name = 'email_confirm'),
	url(r'^login/?',views.login_view,name='login'),
	url(r'^update_location/?',views.update_location,name='update_location'),
	url(r'^update_safe_status/?',views.update_safe_status,name='update-safe_status'),

]