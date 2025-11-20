from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    # In production, run with debug=False
    socketio.run(app, debug=False)
