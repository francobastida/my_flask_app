from flask import render_template, flash, redirect, url_for, request
from flaskapp import app, db
from flaskapp.models import BlogPost, IpView, Day, UkData
from flaskapp.forms import PostForm
from sqlalchemy import func
import datetime

import pandas as pd
import json
import plotly
import plotly.express as px


# Route for the home page, which is where the blog posts will be shown
@app.route("/")
@app.route("/home")
def home():
    # Querying all blog posts from the database
    posts = BlogPost.query.all()
    return render_template('home.html', posts=posts)


# Route for the about page
@app.route("/about")
def about():
    return render_template('about.html', title='About page')


# Route to where users add posts (needs to accept get and post requests)
@app.route("/post/new", methods=['GET', 'POST'])
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = BlogPost(title=form.title.data, content=form.content.data, user_id=1)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post', form=form)


# Route to the dashboard page
@app.route('/dashboard')
def dashboard():
    days = Day.query.all()
    df = pd.DataFrame([{'Date': day.id, 'Page views': day.views} for day in days])

    fig = px.bar(df, x='Date', y='Page views')

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template('dashboard.html', title='Page views per day', graphJSON=graphJSON)

@app.route('/uk_charts')
def uk_charts():
    ukdata = UkData.query.limit(20).all()  # limit for readability

    names = [row.constituency_name for row in ukdata]
    turnout = [row.Turnout19 for row in ukdata]
    con_votes = [row.ConVote19 for row in ukdata]
    lab_votes = [row.LabVote19 for row in ukdata]

    return render_template(
        'uk_charts.html',
        names=names,
        turnout=turnout,
        con_votes=con_votes,
        lab_votes=lab_votes,
        title='UK Elections'
    )

@app.route('/regional_analysis')
def regional_analysis():
    regions = db.session.query(UkData.region).distinct().order_by(UkData.region).all()
    regions = [r[0] for r in regions]
    
    #Initialize lists to regional vote per party
    regional_con_votes = []
    regional_lab_votes = []
    regional_libdem_votes = []
    regional_green_votes = []
    regional_snp_votes = []
    regional_pc_votes = []
    regional_brexit_votes = []
    
    for region in regions:
        regional_totals = db.session.query(
            func.sum(UkData.ConVote19).label('con_total'),
            func.sum(UkData.LabVote19).label('lab_total'),
            func.sum(UkData.LDVote19).label('libdem_total'),
            func.sum(UkData.GreenVote19).label('green_total'),
            func.sum(UkData.SNPVote19).label('snp_total'),
            func.sum(UkData.PCVote19).label('pc_total'),
            func.sum(UkData.BrexitVote19).label('brexit_total'),
            func.sum(UkData.TotalVote19).label('total_votes')
        ).filter(UkData.region == region).first()
        
        total_votes = regional_totals.total_votes or 0
        
        if total_votes > 0:
            regional_con_votes.append((regional_totals.con_total or 0) / total_votes * 100)
            regional_lab_votes.append((regional_totals.lab_total or 0) / total_votes * 100)
            regional_libdem_votes.append((regional_totals.libdem_total or 0) / total_votes * 100)
            regional_green_votes.append((regional_totals.green_total or 0) / total_votes * 100)
            regional_snp_votes.append((regional_totals.snp_total or 0) / total_votes * 100)
            regional_pc_votes.append((regional_totals.pc_total or 0) / total_votes * 100)
            regional_brexit_votes.append((regional_totals.brexit_total or 0) / total_votes * 100)
        
        else:
            regional_con_votes.append(0)
            regional_lab_votes.append(0)
            regional_libdem_votes.append(0)
            regional_green_votes.append(0)
            regional_snp_votes.append(0)
            regional_pc_votes.append(0)
            regional_brexit_votes.append(0)
    
    constituencies = db.session.query(UkData).all()
    names = [c.constituency_name for c in constituencies]
    turnout = [c.Turnout19 for c in constituencies]
    con_votes = [c.ConVote19 for c in constituencies]
    lab_votes = [c.LabVote19 for c in constituencies]
    
    return render_template(
        'regional_analysis.html',
        title='UK 2019 Election Analysis',
        names=names,
        turnout=turnout,
        con_votes=con_votes,
        lab_votes=lab_votes,
        #Add new data
        regions=regions,
        regional_con_votes=regional_con_votes,
        regional_lab_votes=regional_lab_votes,
        regional_libdem_votes=regional_libdem_votes,
        regional_green_votes=regional_green_votes,
        regional_snp_votes=regional_snp_votes,
        regional_pc_votes=regional_pc_votes,
        regional_brexit_votes=regional_brexit_votes
    )

@app.route('/conservative_turnout')
def conservative_turnout():
    # Get all distinct regions
    regions_query = db.session.query(UkData.region).distinct().all()
    regions = [r[0] for r in regions_query]

    retired_pct = []
    con_vote_share = []
    turnout_pct = []

    for region in regions:
        data = db.session.query(
            func.avg(UkData.c11Retired).label('avg_retired'),
            func.sum(UkData.ConVote19).label('con_total'),
            func.sum(UkData.TotalVote19).label('vote_total'),
            func.avg(UkData.Turnout19).label('avg_turnout')
        ).filter(UkData.region == region).first()

        total_votes = data.vote_total or 0
        con_share = (data.con_total / total_votes * 100) if total_votes > 0 else 0

        retired_pct.append(data.avg_retired or 0)
        con_vote_share.append(con_share)
        turnout_pct.append(data.avg_turnout or 0)

    return render_template(
        'conservative_turnout.html',
        title='Retired Population and Voting Behavior',
        regions=regions,
        retired=retired_pct,
        con_share=con_vote_share,
        turnout=turnout_pct
    )

@app.before_request
def before_request_func():
    day_id = datetime.date.today()  # get our day_id
    client_ip = request.remote_addr  # get the ip address of where the client request came from

    query = Day.query.filter_by(id=day_id)  # try to get the row associated to the current day
    if query.count() > 0:
        # the current day is already in table, simply increment its views
        current_day = query.first()
        current_day.views += 1
    else:
        # the current day does not exist, it's the first view for the day.
        current_day = Day(id=day_id, views=1)
        db.session.add(current_day)  # insert a new day into the day table

    query = IpView.query.filter_by(ip=client_ip, date_id=day_id)
    if query.count() == 0:  # check if it's the first time a viewer from this ip address is viewing the website
        ip_view = IpView(ip=client_ip, date_id=day_id)
        db.session.add(ip_view)  # insert into the ip_view table

    db.session.commit()  # commit all the changes to the database
