import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress verbose logging
os.environ["HTTIMEOUT"] = "1"
import logging
logging.disable(logging.CRITICAL)

from app import create_app
from services.supabase_client import get_supabase_service

app = create_app()

with app.app_context():
    sb = get_supabase_service()
    
    admin_id = None
    try:
        resp = sb.auth.admin.create_user({
            'email': 'chinaindiatesting@gmail.com',
            'password': 'others@2024',
            'email_confirm': True
        })
        admin_id = resp.user.id
        print(f'OK Admin user created: {admin_id}')
    except:
        users = sb.table('user_profiles').select('user_id').limit(5).execute()
        admin_id = users.data[0]['user_id'] if users.data else None
        print(f'OK Using existing user: {admin_id}')
    
    if not admin_id:
        admin_id = "ef2f1e5f-0239-447c-9e2f-d1c33bfef351"
    
    # Profile
    existing = sb.table('user_profiles').select('id').eq('user_id', admin_id).limit(1).execute()
    if not existing.data:
        sb.table('user_profiles').insert({
            'user_id': admin_id, 'display_name': 'Admin',
            'avatar_url': 'chinaindiatesting@gmail.com',
            'tier': 'placement', 'onboarding_complete': True
        }).execute()
    else:
        sb.table('user_profiles').update({
            'tier': 'placement', 'onboarding_complete': True,
            'avatar_url': 'chinaindiatesting@gmail.com'
        }).eq('user_id', admin_id).execute()
    print('OK Profile done')
    
    # Curriculum
    topic = sb.table('topics').select('id').eq('slug', 'web-scraping-python').limit(1).execute()
    topic_id = topic.data[0]['id']
    
    curricula = sb.table('curricula').select('id').eq('topic_id', topic_id).limit(1).execute()
    curr_id = curricula.data[0]['id'] if curricula.data else sb.table('curricula').insert({'topic_id': topic_id, 'total_days': 30}).execute().data[0]['id']
    
    titles = ['Introduction & Setup', 'Core Concepts', 'First Project', 'Advanced Techniques', 'Real-World Application']
    for day in range(1, 6):
        existing = sb.table('curriculum_days').select('id').eq('curriculum_id', curr_id).eq('day_number', day).limit(1).execute()
        if not existing.data:
            sb.table('curriculum_days').insert({
                'curriculum_id': curr_id, 'day_number': day, 'title': titles[day-1],
                'description': f'Day {day}: Learn key concepts and build practical skills',
                'learning_objectives': 'Understand fundamentals',
                'practice_task': f'Hands-on exercise Day {day}',
                'apply_task': f'Real-world task Day {day}',
                'video_title': f'Day {day} of Web Scraping — Complete Guide',
            }).execute()
    print('OK Curriculum + days done')
    
    # Cohort
    cohorts = sb.table('cohorts').select('id').eq('name', 'Web Scraping — July 2026 (Test)').limit(1).execute()
    if cohorts.data:
        cohort_id = cohorts.data[0]['id']
    else:
        cohort_id = sb.table('cohorts').insert({
            'topic_id': topic_id, 'curriculum_id': curr_id,
            'name': 'Web Scraping — July 2026 (Test)',
            'start_date': '2026-07-15', 'end_date': '2026-08-14',
            'current_day': 2, 'max_days': 30, 'status': 'active'
        }).execute().data[0]['id']
    
    for day in range(1, 4):
        existing = sb.table('cohort_videos').select('id').eq('cohort_id', cohort_id).eq('day_number', day).limit(1).execute()
        if not existing.data:
            sb.table('cohort_videos').insert({
                'cohort_id': cohort_id, 'day_number': day,
                'youtube_title': f'Day {day}: Web Scraping Fundamentals',
                'youtube_url': f'https://www.youtube.com/watch?v=test{day}' if day < 3 else None,
                'production_status': 'ready' if day < 3 else 'pending',
            }).execute()
    print('OK Cohort + videos done')
    
    # Assign user
    sb.table('user_profiles').update({'cohort_id': cohort_id, 'selected_topic_id': topic_id}).eq('user_id', admin_id).execute()
    
    # Pipeline
    existing = sb.table('freelance_pipeline').select('id').eq('user_id', admin_id).eq('topic', 'web-scraping-python').limit(1).execute()
    if not existing.data:
        sb.table('freelance_pipeline').insert({
            'user_id': admin_id, 'topic': 'web-scraping-python',
            'stage': 'applying', 'proposals_sent': 6,
            'responses_received': 2, 'interviews_held': 1,
            'contracts_won': 1, 'total_earned': 400,
        }).execute()
    print('OK Pipeline done')
    
    # Contracts
    for client, project, value, hrs in [
        ("TechStart Inc", "Data extraction script", 150, 5),
        ("WebAgency Co", "Competitor price scraper", 250, 8),
    ]:
        existing = sb.table('contracts').select('id').eq('user_id', admin_id).eq('project_title', project).limit(1).execute()
        if not existing.data:
            sb.table('contracts').insert({
                'user_id': admin_id, 'platform': 'upwork',
                'client_name': client, 'project_title': project,
                'contract_value': value, 'hours_worked': hrs,
                'start_date': '2026-07-10', 'end_date': '2026-07-14',
                'status': 'completed', 'payment_received': True,
            }).execute()
    print('OK Contracts done')
    
    # Topic intelligence
    existing = sb.table('topic_intelligence').select('topic').eq('topic', 'web-scraping-python').limit(1).execute()
    if not existing.data:
        sb.table('topic_intelligence').insert({
            'topic': 'web-scraping-python', 'freelance_job_count': 247,
            'avg_rate': 30.0, 'demand_trend': 'growing',
            'total_enrolled': 12, 'completion_rate': 0.75,
            'placement_rate': 0.87, 'avg_days_to_first_contract': 28,
            'avg_first_contract_value': 250.0, 'viability_score': 92
        }).execute()
    
    # Progress
    ready_video = sb.table('cohort_videos').select('id').eq('cohort_id', cohort_id).eq('day_number', 1).limit(1).execute()
    if ready_video.data:
        existing = sb.table('user_progress').select('id').eq('user_id', admin_id).eq('cohort_video_id', ready_video.data[0]['id']).limit(1).execute()
        if not existing.data:
            sb.table('user_progress').insert({
                'user_id': admin_id, 'cohort_video_id': ready_video.data[0]['id'],
                'day_number': 1, 'video_watched': True,
                'practice_completed': True, 'apply_completed': True, 'self_rating': 4,
            }).execute()
    
    print()
    print('DONE All test data seeded!')
    print(f'Login: chinaindiatesting@gmail.com / others@2024')
    print(f'Dashboard: Day 2 (Day 1 complete)')
    print(f'Pipeline: 6 proposals, 2 contracts, $400 earned')
