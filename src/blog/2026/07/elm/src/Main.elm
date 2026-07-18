module Main exposing (main)

import Browser
import Html exposing (Html, div, p, text)
import Random

main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = \_ -> Sub.none
        , view = view
        }

-- MODEL

type alias Model =
    { randomNumber : Int }

init : () -> ( Model, Cmd Msg )
init _ =
    ( { randomNumber = 1 }
    , Random.generate NewRandomNumber (Random.int 1 1000)
    )

-- UPDATE

type Msg
    = NewRandomNumber Int

update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        NewRandomNumber newInt ->
            ( { model | randomNumber = newInt }
            , Cmd.none
            )

-- VIEW

view : Model -> Html Msg
view model =
    div []
        [ p [] [ text ("Your initial random number is: " ++ String.fromInt model.randomNumber) ]
        ]
