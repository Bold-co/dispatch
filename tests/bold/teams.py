from dispatch.incident.service import get_teams

teams = get_teams()


for team in teams:
    print(team['name'])
