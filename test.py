import random as rnd


def load_songs(filename):
    with open(filename) as fp:
        return [line.strip() for line in fp if line.strip()]


def song_fight(song1, song2):
    print(f"\n1: {song1}")
    print(f"2: {song2}")

    while True:
        choice = input("Enter 1 or 2 to choose the winner: ").strip()
        if choice == '1':
            return song1
        elif choice == '2':
            return song2
        else:
            print("Invalid input. Please enter 1 or 2.")


def run_tournament(songs):
    round_num = 1

    while len(songs) > 1:
        print(f"\n--- ROUND {round_num} BEGINS ---")
        print(f"Songs remaining: {len(songs)}")

        # Shuffle so matchups are random this round
        rnd.shuffle(songs)
        winners = []

        # Pop two songs at a time to battle
        while len(songs) >= 2:
            song1 = songs.pop()
            song2 = songs.pop()

            winner = song_fight(song1, song2)
            winners.append(winner)
            print(f"{winner} advances!")

        # If there's an odd song out, it gets an automatic bye to the next round
        if len(songs) == 1:
            bye_song = songs.pop()
            winners.append(bye_song)
            print(f"{bye_song} gets a bye to the next round!")

        songs = winners
        round_num += 1

    return songs[0]


def main():
    songs = load_songs("Songs_test")

    if len(songs) < 2:
        print("Not enough songs to run a tournament!")
        return

    ultimate_winner = run_tournament(songs)
    print(f"\n🏆 THE ULTIMATE WINNER IS: {ultimate_winner} 🏆")


if __name__ == "__main__":
    main()