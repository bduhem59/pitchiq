from understatapi import UnderstatClient

leagues = ['EPL', 'La_Liga', 'Bundesliga', 'Serie_A', 'Ligue_1']

with UnderstatClient() as u:
    for league in leagues:
        try:
            players = u.league(league=league).get_player_data(season='2025')
            print(f'{league}: {len(players)} joueurs')
        except Exception as e:
            print(f'{league}: ERREUR - {e}')
