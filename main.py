from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime, timedelta
import uuid


app = FastAPI()

players = {}  # Список игроков, ожидающих партию
games = {}  # Активные игры
players_last_activity = {}  # {'player_id': datetime}


class Player(BaseModel):
    id: str
    name: str
    status: str
    
class Move(BaseModel):
    player_id: str
    move: str  # "rock", "paper", "scissors"

# Обновляем активность игрока
def update_player_activity(player_id):
    players_last_activity[player_id] = datetime.now()

# Функция для удаления неактивных игроков
def remove_inactive_players():
    now = datetime.now()
    to_remove = [player_id for player_id, last_activity in players_last_activity.items() if now - last_activity > timedelta(seconds=20)]
    for player_id in to_remove:
        if player_id in players:
            del players[player_id]
        if player_id in players_last_activity:
            del players_last_activity[player_id]




@app.post("/join")
async def add_player(request: dict):
    print("Получен запрос:", request)
    player_id = request.get("id")
    player_name = request.get("name")

    if not player_id or not player_name:
        raise HTTPException(status_code=422, detail="Player ID and name are required")

    if player_id in players:
        raise HTTPException(status_code=400, detail="Player already exists")

    # Добавляем игрока со статусом "waiting"
    players[player_id] = {
        "name": player_name,
        "status": "waiting"
    }

    return {"message": f"Player {player_name} added successfully"}

@app.get("/players", response_model=List[Player])
def get_players():
    players_list = [{"id": player_id, "name": player_data["name"], "status": player_data["status"]} for player_id, player_data in players.items()]
    return players_list

@app.post("/invite_player")
async def invite_player(invite: dict):
    inviter_id = invite['inviter_id']
    invitee_id = invite['invitee_id']
    
    # Обновляем статус приглашенного игрока на "invited"
    if invitee_id in players:
        players[invitee_id]['status'] = 'invited'
        players[invitee_id]['inviter_id'] = inviter_id
        players[invitee_id]['inviter_name'] = players[inviter_id]['name']
        return {"message": "Invite sent"}
    return {"error": "Invitee not found"}, 404


@app.post("/start_game")
async def start_game(request: dict):
    print("Получен запрос:", request)
    player1_id = request.get("player1_id")
    player2_id = request.get("player2_id")

    if not player1_id or not player2_id:
        raise HTTPException(status_code=422, detail="Both player1_id and player2_id are required")

    if player2_id not in players or players[player2_id]["status"] == "in_game":
        raise HTTPException(status_code=400, detail="Player is already in game or not found")

    # Обновляем статус обоих игроков
    players[player1_id]["status"] = "in_game"
    players[player2_id]["status"] = "in_game"

    game_id = str(uuid.uuid4())  # Генерация уникального ID игры

    games[game_id] = {  # Добавление игры в словарь games
        "player1_id": player1_id,
        "player2_id": player2_id,
        'winner': 'None',
        "moves": {}  # Пустой словарь для хранения ходов
    }

    print("Создана игра:", game_id)
    return {"game_id": game_id}

@app.get("/player_status/{player_id}")
async def player_status(player_id: str):
    # Проверяем, есть ли такой игрок
    if player_id not in players:
        return {"error": "Player not found"}
    
    player_status = players[player_id]['status']
    
    if player_status == 'in_game':
        game_id = None
        for g_id, game in games.items():
            if game['player1_id'] == player_id or game['player2_id'] == player_id:
                game_id = g_id
                break
        
        return {"status": player_status, "game_id": game_id, "opponent_id": game['player1_id']}
    
    if player_status == 'invited':
        return {"status": player_status, "inviter_id": players[player_id]['inviter_id'], "inviter_name": players[player_id]['inviter_name']}
    
    # Если игрок не в игре, возвращаем только статус
    return {"status": player_status}


@app.post("/make_move")
async def make_move(request: dict):
    print("Получен запрос:", request)
    player_id = request.get("player_id")
    game_id = request.get("game_id")
    choice = request.get("choice")

    # Проверяем наличие игры
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    print("Игра:", game_id)
    
    game = games[game_id]


    print("Игрок:", player_id)
    print("Ход:", choice)
    game['moves'][player_id] = choice

    # Логика завершения игры (если оба игрока сделали ход)
    if len(game['moves']) == 2:
        player1_choice = game['moves'][game['player1_id']]
        player2_choice = game['moves'][game['player2_id']]
        
        winner = determine_winner(player1_choice, player2_choice)  # Функция для определения победителя
        if winner == "player1":
            winner = game['player1_id']
        if winner == "player2":
            winner = game['player2_id']

        game['winner'] = winner
        
        print(f"Game {game_id}: {game['player1_id']} chose {player1_choice}, {game['player2_id']} chose {player2_choice}. Winner: {winner}")
        return {"winner": winner}
    
    
    return {"status": "waiting_for_opponent"}

# Обработчик проверки состояния игры
@app.get("/game_status/{game_id}")
async def game_status(game_id: str):
    # Проверяем наличие игры
    if game_id not in games:
        raise HTTPException(status_code=404, detail="Game not found")

    game = games[game_id]

    print("Получен запрос статуса игры: ", game['winner'])

    return {"winner": game['winner']}

def finish_game(game_id, winner_id):
    if game_id in games:
        games[game_id]['winner'] = winner_id

@app.post("/end_game")
async def end_game(request: dict):
    print("Получен запрос:", request)
    player1_id = request.get("player1_id")
    player2_id = request.get("player2_id")

    if not player1_id or not player2_id:
        raise HTTPException(status_code=422, detail="Both player1_id and player2_id are required")

    players[player1_id]["status"] = "waiting"
    players[player2_id]["status"] = "waiting"

    return {"message": "Game ended"}

@app.get("/game/{game_id}")
def get_game(game_id: str):
    return games.get(game_id, {"message": "Game not found"})


def determine_winner(player1_choice, player2_choice):
    if player1_choice == player2_choice:
        return "draw"

    wins = {
        "rock": "scissors",
        "scissors": "paper",
        "paper": "rock"
    }

    if wins[player1_choice] == player2_choice:
        return "player1"
    else:
        return "player2"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
