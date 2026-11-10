%Outputs the states of the experiments in which the compound is active
%(in stable state the function's input is the observed state itself, so the
%counterpart of the time-series "previous observation" is the same observation)
#const compound = c.

%Define
previous_observation(E,C,S) :- curated_observation(E,C,S),
  curated_observation(E,compound,1).

%Display
#show previous_observation/3.
