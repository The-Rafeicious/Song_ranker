import random as rnd

def song_fight(SONG_VS):
    print(SONG_VS["song1"] + " VS. " + SONG_VS["song2"])

def rnd_song (SONG_VS):
    random_num1 = rnd.randint(0, 5)
    random_num2 = rnd.randint(0, 5)

    print(random_num1, random_num2)

    with open("Songs_test") as fp:
        for i, line in enumerate(fp):
            if i == random_num1:
                SONG_VS["song1"] = line.strip()
            if i == random_num2:
                SONG_VS["song2"] = line.strip()
        return SONG_VS

def check_song(SONG_VS):
    song1 = SONG_VS["song1"]
    song2 = SONG_VS["song2"]
    if song1 == song2:
        return False
    elif song1 == "fail":
        return "fail"
    elif song2 == "fail":
        return "fail"
    elif song1 != song2:
        return True

def main():
    SONG_VS = {
        "song1": "fail",
        "song2": "fail",
    }
    SONG_VS = rnd_song(SONG_VS)
    check_state = check_song(SONG_VS)
    if check_state == "fail":
        print("failed, error no song picked")
    elif check_state == True:
        print("song picked")
        song_fight(SONG_VS)
    elif check_state == False:
        print("redo")
        main()


if __name__ == "__main__":
    main()
