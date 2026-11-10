vertex(cyca).
vertex(rb).
vertex(cycb).
vertex(cdc20).
vertex(cdh1).
vertex(cycd).
vertex(cyce).
vertex(e2f).
vertex(p27).
vertex(ubch10).

edge(cycb, cdc20, 1).
edge(rb, cyca, 0).
edge(cyca, cyca, 1).
edge(cdc20, cyca, 0).
edge(cdh1, cyca, 0).
edge(ubch10, cyca, 0).
edge(e2f, cyca, 1).
edge(cdc20, cycb, 0).
edge(cdh1, cycb, 0).
edge(cycd, cycd, 1).
edge(rb, cyce, 0).
edge(e2f, cyce, 1).
edge(rb, e2f, 0).
edge(cyca, e2f, 0).
edge(cycb, e2f, 0).
edge(p27, e2f, 1).
edge(cycd, rb, 0).
edge(cyce, rb, 0).
edge(cyca, rb, 0).
edge(cycb, rb, 0).
edge(p27, rb, 1).
edge(cdc20, ubch10, 1).
edge(ubch10, ubch10, 1).
edge(cycb, ubch10, 1).
edge(cyca, ubch10, 1).
edge(cdh1, ubch10, 0).
edge(cyca, cdh1, 0).
edge(cycb, cdh1, 0).
edge(p27, cdh1, 1).
edge(cdc20, cdh1, 1).
edge(cycd, p27, 0).
edge(cyce, p27, 0).
edge(cyca, p27, 0).
edge(cycb, p27, 0).
edge(p27, p27, 1).
edge(ubch10, cdc20, 1).
edge(cdh1, cdh1, 1).
edge(cycb, cyca, 0).
edge(cdc20, e2f, 1).
edge(e2f, rb, 1).
edge(rb, rb, 0).
edge(p27, ubch10, 1).
functionOr(cdc20, 1..2).
functionAnd(cdc20, 1, cycb).
functionAnd(cdc20, 2, ubch10).
functionOr(cdh1, 1).
functionAnd(cdh1, 1, cdc20).
functionAnd(cdh1, 1, cyca).
functionAnd(cdh1, 1, cycb).
functionAnd(cdh1, 1, p27).
functionAnd(cdh1, 1, cdh1).
functionOr(cyca, 1).
functionAnd(cyca, 1, cdc20).
functionAnd(cyca, 1, cdh1).
functionAnd(cyca, 1, cyca).
functionAnd(cyca, 1, e2f).
functionAnd(cyca, 1, rb).
functionAnd(cyca, 1, ubch10).
functionAnd(cyca, 1, cycb).
functionOr(cycb, 1).
functionAnd(cycb, 1, cdc20).
functionAnd(cycb, 1, cdh1).
functionOr(cycd, 1).
functionAnd(cycd, 1, cycd).
functionOr(cyce, 1).
functionAnd(cyce, 1, rb).
functionAnd(cyce, 1, e2f).
functionOr(e2f, 1..2).
functionAnd(e2f, 1, cyca).
functionAnd(e2f, 1, cycb).
functionAnd(e2f, 1, p27).
functionAnd(e2f, 1, rb).
functionAnd(e2f, 2, cyca).
functionAnd(e2f, 2, p27).
functionAnd(e2f, 2, rb).
functionAnd(e2f, 2, cdc20).
functionOr(p27, 1..3).
functionAnd(p27, 1, cycd).
functionAnd(p27, 1, cyce).
functionAnd(p27, 1, cyca).
functionAnd(p27, 1, cycb).
functionAnd(p27, 2, cycd).
functionAnd(p27, 2, cyca).
functionAnd(p27, 2, p27).
functionAnd(p27, 2, cycb).
functionAnd(p27, 3, cycd).
functionAnd(p27, 3, cyce).
functionAnd(p27, 3, p27).
functionAnd(p27, 3, cycb).
functionOr(rb, 1).
functionAnd(rb, 1, cyca).
functionAnd(rb, 1, cycb).
functionAnd(rb, 1, cycd).
functionAnd(rb, 1, cyce).
functionAnd(rb, 1, p27).
functionAnd(rb, 1, e2f).
functionAnd(rb, 1, rb).
functionOr(ubch10, 1).
functionAnd(ubch10, 1, cdc20).
functionAnd(ubch10, 1, cdh1).
functionAnd(ubch10, 1, cyca).
functionAnd(ubch10, 1, cycb).
functionAnd(ubch10, 1, ubch10).
functionAnd(ubch10, 1, p27).
