%Generates the optimal candidate function for synchronous observations.
%(In synchronous mode, all functions are actived at each time step. As such,
%we must ensure that, at each time step, the compound's function
%is able to replicate the observed state).

#const compound = c.
#const node_number = n.

%*--Fixing regulators--*%
%fixed/2 tells us that regulator C has to be one of the compound's regulators
fixed_regulator(C) :- fixed(C,compound), compound(C).
fixed_regulator(C) :- fixed(C,compound,_), compound(C).

%Fixed/3. contains information regarding the sign of a fixed regulator
fixed_activator(C) :- fixed(C,compound,0), compound(C).
fixed_inhibitor(C) :- fixed(C,compound,1), compound(C).

%*--Assigning regulator signs--*%
%Fixed activators and inhibitors already have their regulation behavior defined
activator(C) :- fixed_activator(C).
inhibitor(C) :- fixed_inhibitor(C).

%A compound C can either be an inhibitor or an activator, but not both
1 {activator(C); inhibitor(C)} 1 :- compound(C), 
  not fixed_activator(C), not fixed_inhibitor(C).

%*--Creating nodes--*%
%Original node IDs must always be available 
%(so that we are able to make as little changes to the format of the original 
%nodes as possible, using optimizations #3). Note that we cannot simply 
%create all IDs using 1..node_number, since node_number may be smaller than
%the number of original nodes. This would cause us to potentially leave out 
%some original nodes when optimizing the format of our solution nodes
available_node_ID(1..TERM_NO) :- function(compound, TERM_NO).

%If we require more IDs than those that were originally available,
%create them
available_node_ID(TERM_NO + 1..node_number):- function(compound, TERM_NO), node_number > TERM_NO.

%Distribute compounds across available IDs
{node_regulator(N,C) : compound(C)} :- available_node_ID(N).

%Project the node IDs our solution is using into their own predicate
node_ID(N) :- node_regulator(N,_).

%If a node N1 has some regulating compound C which is not present in node N2,
%then N1 is distinct from N2 (used in IC #3)
distinct_nodes(N1,N2) :- node_regulator(N1,C), node_ID(N2), N1 < N2, not node_regulator(N2,C). 

%*--Assessing node behavior--*%
%If one of a node N's regulators has value 0 for experiment E at time step T, 
%then for that same experiment and time step the node will also have value 0 (if that variable is an activator)
timestep_negative_node(E,T,N) :- node_regulator(N,C), curated_observation(E,T,C,0), activator(C).
%Variant for variables that are inhibitors
timestep_negative_node(E,T,N) :- node_regulator(N,C), curated_observation(E,T,C,1), inhibitor(C).

%Nodes that aren't negative (i.e. have value 0) at time step T of experiment E must be positive (i.e. have value 1)
timestep_positive_node(E,T,N) :- not timestep_negative_node(E,T,N), node_ID(N), curated_observation(E,T,_,_).

%Test
%1-We're only interested in generating nodes that can be used to explain the observations,
%which is not possible for a node to do if it is positive when we expect it to be negative
:- timestep_positive_node(E,T-1,N), curated_observation(E,T,compound,0), T > 0.

%2-Every positive observation must be covered by some positive node
:- not timestep_positive_node(E,T-1,_), unique_positive_observation(E,T).

%3-Candidate nodes must be distinct
:- node_ID(N1), node_ID(N2), N1 < N2, not distinct_nodes(N1,N2).

%4-The BCF cannot be broken (nodes cannot contain other nodes)
:- N1_VARNO = #count{ C : node_regulator(N1,C) }, 
  COMMON_VARNO = #count{C : node_regulator(N1,C), node_regulator(N2,C)},   
  node_ID(N1), node_ID(N2), N1 != N2, COMMON_VARNO = N1_VARNO.
  
%5-Fixed regulators must be present in the final solution
:- fixed_regulator(C), not node_regulator(_,C).

%6-We must always have node_number nodes in our solution
:- node_number != #count{N : node_regulator(N,R)}.

% 7 - New used node IDs must be continuous
% In other words, if an available id higher than another id is used than the lower id must also be used
:- node_ID(N2), available_node_ID(N1), N2 > N1, not node_ID(N1), function(compound, TERM_NO), 
          N2 > TERM_NO.

%Display
regulator_activator(C) :- node_regulator(N,C), activator(C).
regulator_inhibitor(C) :- node_regulator(N,C), inhibitor(C).

#show node_ID/1.
#show regulator_activator/1.
#show regulator_inhibitor/1.
#show node_regulator/2.

