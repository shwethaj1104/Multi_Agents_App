#import <AppKit/AppKit.h>
// Rebuild: clang -framework AppKit developer-guide/diagrams/render.m -o /tmp/loandesk-render && /tmp/loandesk-render
CGFloat height=2200;
NSColor *navy,*blue,*green,*amber;
NSRect rect(CGFloat x,CGFloat y,CGFloat w,CGFloat h){return NSMakeRect(x,height-y-h,w,h);}
void text(NSString*s,CGFloat x,CGFloat y,CGFloat w,CGFloat size,BOOL bold){NSMutableParagraphStyle*p=[NSMutableParagraphStyle new];p.alignment=NSTextAlignmentCenter;[s drawInRect:rect(x,y,w,200) withAttributes:@{NSFontAttributeName:bold?[NSFont boldSystemFontOfSize:size]:[NSFont systemFontOfSize:size],NSForegroundColorAttributeName:navy,NSParagraphStyleAttributeName:p}];}
void card(NSString*t,NSString*d,CGFloat x,CGFloat y,CGFloat w,CGFloat h,NSColor*c){[c setFill];NSBezierPath*p=[NSBezierPath bezierPathWithRoundedRect:rect(x,y,w,h) xRadius:18 yRadius:18];[p fill];[[navy colorWithAlphaComponent:0.25] setStroke];p.lineWidth=2;[p stroke];text(t,x+20,y+19,w-40,30,YES);text(d,x+25,y+70,w-50,26,NO);}
void drawBox(NSString*t,NSString*d,CGFloat y,CGFloat h,NSColor*c){card(t,d,220,y,1160,h,c);}
void line(CGFloat x,CGFloat y,CGFloat xx,CGFloat yy,BOOL tip){[navy setStroke];NSBezierPath*p=[NSBezierPath bezierPath];p.lineWidth=3;[p moveToPoint:NSMakePoint(x,height-y)];[p lineToPoint:NSMakePoint(xx,height-yy)];if(tip){CGFloat a=atan2(yy-y,xx-x);[p moveToPoint:NSMakePoint(xx-16*cos(a-0.55),height-(yy-16*sin(a-0.55)))];[p lineToPoint:NSMakePoint(xx,height-yy)];[p lineToPoint:NSMakePoint(xx-16*cos(a+0.55),height-(yy-16*sin(a+0.55)))];}[p stroke];}
void arrow(CGFloat a,CGFloat b){line(800,a,800,b,YES);}
void render(BOOL multi,NSString*filename){NSBitmapImageRep*b=[[NSBitmapImageRep alloc] initWithBitmapDataPlanes:NULL pixelsWide:1600 pixelsHigh:2200 bitsPerSample:8 samplesPerPixel:4 hasAlpha:YES isPlanar:NO colorSpaceName:NSDeviceRGBColorSpace bytesPerRow:0 bitsPerPixel:0];[NSGraphicsContext saveGraphicsState];[NSGraphicsContext setCurrentContext:[NSGraphicsContext graphicsContextWithBitmapImageRep:b]];[[NSColor colorWithWhite:0.97 alpha:1] setFill];NSRectFill(NSMakeRect(0,0,1600,2200));
text(@"LOANDESK",100,35,1400,24,YES);
text(multi?@"Supervisor + parallel specialists":@"Single-agent loan review",80,80,1440,46,YES);
text(multi?@"LangGraph orchestrates • LangChain builds the agents":@"One LangChain agent • LangGraph manages state and approval",80,145,1440,27,NO);
drawBox(@"Upload the same business loan application",@"Loan request + financial statements + bank transactions",225,145,[NSColor whiteColor]);arrow(370,415);
drawBox(@"Prepare shared case data — ordinary code",@"Read documents and expose the same evidence, policy and calculation tools",415,145,[NSColor whiteColor]);arrow(560,610);
if(multi){
drawBox(@"SUPERVISOR — dispatch inside LangGraph",@"Code dispatches fixed tasks; model plans only targeted feedback",610,145,green);
line(800,755,800,815,NO);line(320,815,1280,815,NO);line(320,815,320,875,YES);line(800,815,800,875,YES);line(1280,815,1280,875,YES);
text(@"Same case data • independent tasks",845,767,650,23,YES);
card(@"DOCUMENT AGENT",@"Check missing files\nCompare document facts\nFlag contradictions\nReturn evidence references",110,875,420,255,blue);
card(@"FINANCIAL AGENT",@"Use calculation tools\nAssess repayment scenarios\nFlag uncertain inputs\nReturn values + assumptions",590,875,420,255,blue);
card(@"POLICY AGENT",@"Retrieve policy clauses\nCheck available eligibility facts\nIdentify required evidence\nFlag pending financial checks",1070,875,420,255,blue);
line(320,1130,320,1180,NO);line(800,1130,800,1180,NO);line(1280,1130,1280,1180,NO);line(320,1180,1280,1180,NO);line(800,1180,800,1230,YES);
drawBox(@"SUPERVISOR — joins all three reviews",@"Match financial results to policy; reconcile conflicts; draft a cited memo",1230,145,green);
} else {
drawBox(@"ONE GENERALIST AGENT",@"Investigate documents → use financial tools → retrieve policy\nChoose follow-up tool calls and revise findings within one agent",610,235,blue);arrow(845,900);
drawBox(@"The same agent assembles the review",@"Connect evidence, financial results and policy requirements\nRecord assumptions, discrepancies and unresolved questions",900,205,blue);arrow(1105,1230);
drawBox(@"Draft a cited review memo",@"Same output format and required evidence as the multi-agent version",1230,145,[NSColor whiteColor]);
}
arrow(1375,1440);
drawBox(@"Resolve gaps before final review",multi?@"Supervisor requests targeted agent follow-up or asks a person for facts":@"The agent investigates further or asks a person for missing facts",1440,145,amber);
// Explicit feedback path: follow-up returns to the agent/supervisor and rechecks dependent findings.
line(220,1512,65,1512,NO);line(65,1512,65,682,NO);line(65,682,220,682,YES);
text(@"Ready for human review",850,1610,500,23,NO);
arrow(1585,1680);
drawBox(@"HUMAN LOAN OFFICER — approval pause",@"Inspect evidence and recommendation\nApprove the memo, request changes, or reject",1680,170,amber);
line(1380,1765,1535,1765,NO);line(1535,1765,1535,1302,NO);line(1535,1302,1380,1302,YES);
text(@"Final decision",850,1872,500,23,NO);
arrow(1850,1930);
drawBox(@"Save the final human decision and audit history",@"Simulated loan review • no automatic loan approval or disbursement",1930,130,green);
text(@"LANGSMITH: agent calls • tool results • handoffs • follow-ups • approvals",80,2090,1440,24,YES);
text(@"SAME EVALUATION: correctness • evidence • cost • processing time • reliability",80,2140,1440,23,NO);
[NSGraphicsContext restoreGraphicsState];[[b representationUsingType:NSBitmapImageFileTypePNG properties:@{}] writeToFile:filename atomically:YES];}
int main(){@autoreleasepool{navy=[NSColor colorWithRed:0.08 green:0.15 blue:0.25 alpha:1];blue=[NSColor colorWithRed:0.90 green:0.95 blue:1 alpha:1];green=[NSColor colorWithRed:0.88 green:0.96 blue:0.92 alpha:1];amber=[NSColor colorWithRed:1 green:0.95 blue:0.84 alpha:1];render(NO,@"developer-guide/diagrams/single-agent-flow.png");render(YES,@"developer-guide/diagrams/multi-agent-flow.png");}return 0;}
