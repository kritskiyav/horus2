from app.parservk import views

# настраиваем пути, которые будут вести к нашей странице
def setup_routes(app):
   app.router.add_get("/", views.index, name='index')
   app.router.add_post("/index_post", views.index_post, name='index_post')
   app.router.add_get("/ticket", views.ticket, name='ticket')