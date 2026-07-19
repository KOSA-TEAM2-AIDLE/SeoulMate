# Attraction train/dev augmentation review queue

각 사례는 SeoulMate DB의 관광 장소 설명·연결 리뷰 원문과 대조한 상태입니다. `reviewed` 사례만 이후 train/dev 반영 후보가 됩니다.

## augmentation-v1-001 — multi_candidate → train

- Question: 어떤 장소에서 생활 도구이면서 조형미를 지닌 그릇과 화기를 만나볼 수 있나요?
- Expected IDs: bo1j5m
- Candidates:
  - `bo1j5m` 오자크래프트 — 오자크래프트는 생활 도구이면서도 조형미를 지닌 그릇과 화기가 늘어서 있어, 크래프트와 아트의 경계를 편안하게 오가는 브랜드의 세계관을 체험할 수 있는 장소입니다. 오자와 제비, 두 작가가 함께 운영하는 브랜드로 다양한 오브제를 만날 수 있을 뿐만 아니라 쇼룸에서 열리는 전시도 감상할 수 있습니다.
  - `5y94vy` GS25 DXLAB점 — GS25 DX LAB&CAFE는 GS25의 프리미엄 편의점으로 편의점인 동시에 카페로 이용이 가능하며, 다른 점포에는 없는 특이하고 특별한 여러 종류의 상품들이 있어 구경하는 재미도 느껴보실 수 있습니다. 카페 이용은 SELF ZONE을 통해 무인으로 운영되고 또한 자정부터 오전 6시까지 무인매장으로 운영됩니다. 위스키와
  - `q52hjp` 가든뷰 — 가든뷰는 서울의 '가든스 바이 더 베이'인 '서울식물원' 인근에 위치하고 있으며 이를 착안하여 구상된 뷰티&헬스 및 오가닉 전문 스토어 입니다. 어느 한 장르에만 해당되지 않는 여러 장르의 상품들을 접할 수 있는 멀티 스토어로 국내외 다양한 브랜드 상품들을 한번에 경험할 수 있어 고객들에게 많은 사랑을 받고 있습니다. 특
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place '오자크래프트' is uniquely supported by the provided evidence, which describes it as a place where functional and sculptural ceramics can be found.

## augmentation-v1-002 — multi_candidate → train

- Question: What type of specialized store offers a variety of unique items related to movies, music, and culture, including rare posters and collectibles?
- Expected IDs: nx3r6c
- Candidates:
  - `nx3r6c` 마이 페이보릿 — 마이페이보릿은 영화를 좋아한다면 굿즈부터 LP까지 취향을 저격하는 영화 전문 편집숍입니다. 영화, 음악, 문화를 체감할 수 있는 공간으로 대중적인 아이템보다 마니아 성향이 강한 아이템을 많이 볼 수 있습니다. 내부는 LP존, 포스터존, 서적존, 지브리존 등으로 세분하고, 파트별로 신현이 대표의 취향이 반영된 희소성 높은 
  - `lh08xy` 롤드페인트 — 돌돌 말려 있는 물감 하나로 일상이 다채로워지는 낭만, 롤드페인트는 마스킹 테이프만 전문적으로 다루는 공간입니다. 브랜드 슬로건인 “Roll your own space.”는 각자의 고유한 공간에 마스킹 테이프로 롤링하는 행위를 통해 몰입의 즐거움과 창작의 기쁨을 즐겨보실 수 있길 바라는 마음이 담겨 있습니다. 일본, 국내
  - `ln64kv` 빈티지숍 페이지원 — 페이지원은 국내외에서 직수입한 의류와 잡화, 소품, 가구 등 다양한 빈티지 아이템을 취급합니다. 빈티지 제품임에도 상품 상태가 매우 뛰어며, 매장 분위기와 어울리는 신제품도 찾아볼 수 있습니다. 1층에는 다양한 빈티지 여성 의류, 소품 등이 있으며, 2층에는 브랜드 빈티지, 수입바잉상품 등을 판매하고 있습니다. 호주 .유
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place 'My Favorite' is uniquely supported by the provided evidence, which describes it as a specialty store for movie-related items, including rare posters and collectibles.

## augmentation-v1-003 — multi_candidate → train

- Question: 어떤 장소에서 K-POP 전문 특화 매장을 경험하고 좋아하는 아티스트의 세계관을 직접 보고, 듣고, 느낄 수 있나요?
- Expected IDs: et9p1i
- Candidates:
  - `et9p1i` 케이팝 스퀘어 홍대 — 외국인 관광객의 인기 방문 코스인 라인프렌즈 홍대 플래그십 스토어가 국내 유일 K-POP 전문 특화 매장 '케이팝 스퀘어 홍대'라는 이름으로 새롭게 리뉴얼해 문을 엽니다. 좋아하는 아티스트의 세계관을 직접 보고, 듣고, 느낄 수 있는 색다른 팝업과 전시, 그리고 한정 굿즈까지 경험해 보세요. 전 세계 K-POP 팬이라면 
  - `6ptemj` 신세계 더 헤리티지 — 신세계 더 헤리티지의 기존 건축물은 한국 최초의 민간 금융 기관으로 1935년 준공되어 1989년, 서울시 유형문화재 제71호로 지정될 만큼 근대건축사의 기념비적 건물로 평가받습니다. 당대 신고전주의 영향을 받아 거대하면서도 안정적이고, 내부는 절제된 화려함을 추구하는 건축양식이 특징입니다. 신세계는 한국적 미 美의 역사
  - `7c8tmq` LOEUVRE 루에브르 한남 플래그십 스토어 — 루에브르(LOEUVRE)는 프렌치 감성을 기반으로 하며 빛과 그림자를 컨셉으로 제품이 표현하는 선과 컬러감, 소재의 중요성에 많은 시간과 공을 들여 ‘작품’과 같은 개념의 제품을 만들어내고자 합니다. 브랜드명은 프랑스어 명사 ‘oeuvre(에브르)‘ + 정관사 ‘le(르)’의 합성어로 Oeuvre의 사전적 의미는 작가나 
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place '케이팝 스퀘어 홍대' is uniquely supported by the provided evidence, which describes it as a specialized K-POP store where fans can experience their favorite artists' worldviews.

## augmentation-v1-004 — multi_candidate → train

- Question: What eyewear brand is known for its futuristic store design and offers a variety of styles with innovative lens technology at reasonable prices?
- Expected IDs: 0nu1y0
- Candidates:
  - `0nu1y0` NEOTERIA 네오텔리아 한남 — 미래적인 분위기가 물씬 풍기는 매장 내부에는 A-Gate, B-Gate, C-Gate라는 세 개의 구역이 구성되어 있으며, 다양한 스타일의 아이웨어 제품들이 한눈에 펼쳐집니다. 시력 보호 기술을 적용한 네오테리아의 갤럭시 렌즈와 초경량 테트론 프레임은 셀룰로이드보다 가볍고, 내구성까지 갖춘 것이 특징입니다. 혁신적인 기술
  - `vvfz6r` 선유도 고양이 — 전세계 고양이의 이야기를 수집한 공간, 선유도 고양이는 고양이와 관련된 전설을 간직한 곳인 선유도에 위치해 있으며, 과거 선유도에는 선유봉이라는 봉우리가 있었고, 그 모양이 고양이를 닮아 '괭이산'이라 불렸습니다. 전세계에서 들여온 고양이 관련 소품과 센스 있는 작가들의 작품을 만날 수 있습니다.
  - `8692xd` 경옥채(瓊玉綵) 한약국 청담점 — 경옥채는 그 약의 효능과 귀함이 남달라 보석의 이름을 갖게 된 경옥고처럼 황제에게 진상하는 귀한 보석과 비단을 만드는 마음으로 한약을 짓겠다는 우리의 다짐. 그리고, 프리미엄 건강 식품 브랜드 '더경옥'을 만든 한약국으로서 앞으로 그 명성과 가치가 보석과 비단처럼 변하지 않고 장수하기를 소망하며 지어진 이름입니다. 지금은
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected selection of NEOTERIA is uniquely supported by the provided evidence, highlighting its futuristic design, innovative lens technology, and reasonable prices.

## augmentation-v1-005 — multi_candidate → dev

- Question: 어떤 장소에서 조미료 없이 한국의 재료를 살려 만든 음식을 제공하며, 다양한 K-Handmade 작품을 만날 수 있나요?
- Expected IDs: 1fhege
- Candidates:
  - `1fhege` 소담상회 with idus place 서교점 — 아시아 NO.1 핸드메이드 플랫폼 idus가 운영하는 캐주얼 다이닝&핸드메이드샵입니다. 조미료 없이 한국의 재료를 살려 만든 음식과 다채로운 K-Handmade 작품을 만나볼 수 있어서 눈과 입이 모두 만족되는 곳입니다. 카페만 이용하는 것도 가능하니 여행 중 휴식이 필요할 때 편하게 들려봐도 좋을 듯 합니다. 이 공간은
  - `54zrmq` 소담상회 with idus place 인사점 — 아시아 NO.1 핸드메이드 플랫폼 idus가 운영하는 핸드메이드샵입니다. 1층 미니샵부터 핸드메이드의 수려함을 더욱 느낄 수 있는 별관, 메인 4층 공간까지 다채로운 핸드메이드 작품을 만나볼 수 있습니다. 전통, 패션, 홈리빙, 반려동물 등 다양한 카테고리가 있고, 이 곳에서만 만나볼 수 있는 작품들도 있어서 취향따라 선
  - `azp76o` 키스 서울 — 1층에는 플라워숍이나 쥬얼리, 라이프 스타일 상품들이 감각적으로 진열되어 있으며, 'SEOUL'로고가 새겨진 타일 바닥은 포토 스팟으로 유명합니다. 2층에는 KITH를 대표하는 스니커즈와 의류 상품으로 채워져 있으며, KITH 자체 브랜드 제품은 물론 셀렉트 브랜드 제품들도 다양하게 갖추고 있어 특별한 선물을 고르기에도 
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID '1fhege' is uniquely supported by the evidence, which states it offers food made with Korean ingredients without seasoning and features K-Handmade works.

## augmentation-v1-006 — multi_candidate → train

- Question: What brand offers a personalized label engraving service for its perfumes, emphasizing a warm and emotional brand philosophy without advertising or celebrity endorsements?
- Expected IDs: 6x3iur
- Candidates:
  - `6x3iur` 그랑핸드 도산 — 한국 향수 브랜드 Granhand는 2014년에 설립된 이후로, 꾸밈없고 감성적이며 따뜻한 브랜드 철학을 유지해오고 있습니다. 광고를 하지 않고, 유명인을 모델로 기용하지 않으며, 포장조차도 소박한 모습입니다. 병에 붙여진 라벨은 손으로 직접 만든 듯한 느낌을 주며, Granhand가 일상에 가까운 브랜드 스타일을 추구한
  - `4rundc` 그로브 — 2020년에 설립된 GROVE는 1960년대 레트로 스타일을 캐주얼 스타일에 접목해 클래식하면서도 담백한 브랜드 스타일을 선보입니다. 뉴진스, 에스파 멤버, 한소희 등 많은 아티스트와 인플루언서들이 GROVE 사복을 입고 등장해 호평을 받았습니다. GROVE는 단 몇 년 만에 20~30대 한국 여성들에게 큰 인기를 끌고 
  - `42q156` 10 꼬르소 꼬모 청담점 — 2008년 압구정에 오픈한 10 Corso Como Seoul은 3층 규모 1,400㎡ 공간에 서점, 디자인, 패션, 음식, 예술이 독창적으로 통합된 복합 문화 공간입니다. 외관은 수많은 기하학적 원형과 유리 벽면으로 디자인되었으며, 안으로 들어서는 순간 화려한 빛과 예술적인 분위기를 느낄 수 있는 서울에서 유명한 패션 
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected selection is uniquely supported by the DB evidence, which describes Granhand's personalized label engraving service and its brand philosophy.

## augmentation-v1-007 — multi_candidate → train

- Question: 이곳은 과거 제화 공장이 밀집했던 지역으로, 현대 감성과 복합문화 공간이 어우러진 거리입니다. 어떤 장소인가요?
- Expected IDs: 7u7jrk
- Candidates:
  - `7u7jrk` 성수 연무장길 — 성수동 연무장길은 서울 성동구에 위치한 복합문화 거리로, 과거 제화 공장이 밀집했던 산업의 흔적과 현대 감성이 어우러진 공간입니다. '연무장'이라는 이름은 조선시대 병사들이 무예를 연습하던 장소에서 유래되었으며 현재는 붉은 벽돌 창고를 개조한 복합문화공간 '대림창고'를 비롯해 감각적인 디자인의 카페, 갤러리, 의류 편집숍
  - `rqbz6d` 용산 용리단길 — 용리단길은 서울 용산의 새로운 트렌드 중심지로, 삼각지역과 신용산역 사이 골목길을 따라 펼쳐진 감성 가득한 복합문화 거리입니다. 과거 낡은 주택과 공업지대였던 이곳은 최근 감각적인 리노베이션을 통해 독특한 매력을 지닌 공간으로 탈바꿈했습니다. SNS에서 핫한 베트남 음식점 ‘효뜨’, 지브리 애니메이션을 연상시키는 브런치 
  - `vxxkpq` 아이헤이트먼데이 — 아이헤이트먼데이 쇼룸은 서울 후암동에 위치한 양말 브랜드 아이헤이트먼데이의 특별한 공간입니다. 2011년 시작된 아이헤이트먼데이는 ‘누구나 싫어하는 월요일을 즐겁게 하자’는 슬로건 아래 감각적이고 개성 넘치는 양말을 비롯한 다양한 제품을 선보이고 있습니다. 이곳 쇼룸에서는 브랜드의 독창적인 디자인과 컬래버레이션 제품들을 
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID '7u7jrk' is uniquely supported by the provided evidence, describing a cultural street that aligns with the question.

## augmentation-v1-008 — multi_candidate → train

- Question: What type of space offers a unique blend of historical significance and modern creativity, providing a variety of books, products, and lifestyle experiences, including a co-working area for creators?
- Expected IDs: slqc0j
- Candidates:
  - `slqc0j` 스틸북스 회현 — 스틸북스 회현은 도시에서 창의적 생산활동을 이어가는 이들에게 영감을 제공하는 특별한 서점입니다. 남대문 시장과 남산 사이, 과거 봉제공장이었던 공간에 위치해 독특한 역사적 흔적과 현대적 감각이 공존합니다. 이곳에서는 큐레이션을 통해 성장의 발판이 될 다양한 책과 제품을 만날 수 있으며, 스몰브랜드와 크리에이터들의 실험적 
  - `0kjpgo` 올라이트 서촌점 — 서촌의 골목길에 자리 잡은 올라이트는 따뜻한 감성을 담은 소품과 문구들로 가득한 아늑한 공간입니다. 아기자기한 다이어리, 엽서, 그리고 선물하기 좋은 소품들까지 다양한 아이템이 방문객의 마음을 사로잡습니다. 특히 벽 한쪽을 가득 채운 수많은 엽서들은 다양한 메시지와 디자인으로 눈길을 끌며, 하나하나가 특별한 이야기를 담고
  - `ia9uar` 어쩌다 책방 — 연남동 어쩌다 책방은 '우연과 상상의 장소'라는 매력적인 주제를 품고 있는 서점입니다. 독자와 작가의 시공이 교차하는 순간에 비로소 모습을 드러내는 이곳은, 단순한 책방을 넘어서는 특별한 공간입니다. 매달 한 명의 작가를 선정하여 그들의 이야기를 소개하며, 방문객들에게 새로운 영감과 경험을 선물합니다. 책방 곳곳에는 느긋
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place '스틸북스 회현' is uniquely supported by the evidence, highlighting its blend of historical significance and modern creativity, along with a co-working area.

## augmentation-v1-009 — multi_candidate → train

- Question: 이곳에서는 편지와 관련된 다양한 제품과 서비스를 제공하며, 펜팔 서비스를 경험할 수 있는 공간은 어디인가요?
- Expected IDs: sy91f2
- Candidates:
  - `sy91f2` 글월 연희점 — "글월"은 '편지'를 의미하는 순우리말로, 편지를 높여 부르는 말이기도 합니다. 2019년부터 서울을 기반으로 편지 가게를 운영하며, 편지와 관련된 다양한 제품과 서비스를 제공하고 있습니다. 글월은 편지 쓰기를 현대 문화의 하나로 만들기 위한 즐거운 시도를 하고 있으며, 편지의 가치와 정신을 이어나가는 것을 목표로 하고 
  - `8jtjh5` 옵틱프로젝트 — OPTIC PROJECT는 모던한 무드를 지향하며, 가변적인 태도로 다가가는 아이웨어 셀렉샵입니다. 즉, 아이웨어(OPTIC)에 근간을 두며 이를 모던하고 세련된 분위기로 큐레이팅하고, 기존의 플레이어들과는 차별화된 무드를 보여주는 공간입니다. 또한 PROJECT라는 단어가 지닌 뜻처럼 멈추어 있지 않은 가변적인 성향의 
  - `g9q2f1` 아셈안경 — 아셈안경원은 스타필드코엑스몰 (2호선삼성역)에 위치하여 별마당도서관, 아쿠아리움 등 관광 및 쇼핑을 즐기실 수 있습니다. 1:1로 진행되는 컨설팅으로 꼼꼼한 검안, 알맞은 렌즈상담 그리고 트랜디한 아이웨어 까지 완성도 높은 서비스를 제공해드립니다. 네이버 에약을 통해 안경피팅케어 및 정밀 콘택트렌즈 검안케어를 서비스 받으
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 'sy91f2' is uniquely supported by the provided evidence, which describes the penpal service and letter-related products offered at '글월 연희점'.

## augmentation-v1-010 — multi_candidate → dev

- Question: What shopping location features a unique architectural design with a high ceiling and a signature sneaker zone, while also hosting various pop-up stores?
- Expected IDs: nh3bjr
- Candidates:
  - `nh3bjr` 무신사 스토어 성수@대림창고 — 무신사 스토어 성수@대림창고는 무신사가 무신사 스토어 대구, 무신사 스토어 홍대에 이어 오프라인 공간에 선보이는 세 번째 공간입니다. 성수에서 약 50여년간 상징적인 공간으로 자리잡고있던 대림창고의 원형을 그대로 보존하며, 불필요한 장식을 배제하고 본질에 충실한 미니멀한 공간으로 재탄생 시켰습니다. 브랜드와 상품이 중심이
  - `1ny5i7` 무신사 엠프티 압구정 베이스먼트 — 무신사 엠프티 압구정 베이스먼트는 성수점에 이어 오픈한 두 번째 매장으로, 가격 측면의 접근성을 높인 것이 특징입니다. 신규 발매 제품은 물론 시즌 오프 제품과 컬래버레이션 제품을 섞어 다채롭게 구성하여, 매장 곳곳에서 나만의 스타일을 직접 발견해 내고 득템하는 즐거움을 느끼실 수 있습니다. 압구정 최대 규모의 편집숍으로
  - `qyg4ls` 마이초이스 서촌 — 우리의 일상 속 가치있는 물건을 소개하자는 취지에서 시작된 마이초이스는 정동에서 시작하여 서촌에서 두 번째 프로젝트를 시작했습니다. <시간이 흘러도 변함없는 가치>를 지닌 제품을 비롯하여 오브제와 가구, 책과 음악에 대한 색다른 경험과 영감을 전달하는 라이프스타일 컨셉스토어입니다. 지하 1층은 가구와 책으로 구성되어있고,
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 'nh3bjr' is uniquely supported by the DB evidence, which describes its unique architectural design, high ceiling, signature sneaker zone, and pop-up stores.

## augmentation-v1-011 — multi_candidate → train

- Question: 어떤 매장에서 나만의 DIY 아이템을 만들고 다양한 문구 제품을 경험할 수 있나요?
- Expected IDs: k0r1d9
- Candidates:
  - `k0r1d9` 모나미스토어 성수점 — 1963년 성수동에서 시작된 모나미 FACTORY가 현재 모나미스토어 성수점으로 오픈했습니다. 해당 매장에서는 모나미를 직접 경험하고 나만의 DIY 아이템을 만들어 색다른 경험을 즐길 수 있는 장소입니다. 볼펜부터 노트, 내가 직접 조립해 만들 수 있는 나만의 볼펜까지 다양한 종류의 제품들을 판매하고 있고 예약 후 진행이
  - `yd4kmy` 진저하우스 — 진저하우스는 서울에서 시작된 아이웨어 브랜드인 '진저아이웨어'의 쇼룸입니다. 이곳에서는 자연스럽고 조화로운 안경을 만들어 선보이기 때문에 누구나 편안한 안경을 착용할 기회를 제공합니다. 진저아이웨어는 편안한 분위기를 빚어내는 안경을 만들고, 보다 친밀하게 다가갈 수 있도록 안경의 특징을 생활 속에서 안경을 착용하는 때에 
  - `xq6vzf` 책방 오늘  — 서촌에 있는 문학과 인문, 예술, 그림책 서점이다. 작가와 함께하는 '메아리 낭독회', 독서 모임과 글쓰기 워크숍, 공연 등 다양한 모임을 개최합니다 .
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 'k0r1d9' is uniquely supported by the evidence, which describes the store as a place to create DIY items and experience various stationery products.

## augmentation-v1-012 — multi_candidate → train

- Question: What global lifestyle brand offers a variety of products including jeans, underwear, and accessories, and has staff who can assist in multiple languages for foreign customers?
- Expected IDs: 4o6xl3
- Candidates:
  - `4o6xl3` 캘빈클라인 홍대점 — Calvin Klein은 대담하고 진보적인 이상과 매혹적인 미학을 보여주는 글로벌 라이프스타일 브랜드입니다. 캘빈클라인 홍대점은 캘빈클라인 진, 언더웨어, 액세서리 등 캘빈클라인에서 전개하는 모든 상품을 경험하고 쇼핑 할 수 있는 Combo Store 입니다. 매장에서 방문하셔서 캘빈클라인의 매력적인 상품들을 만나보세요.
  - `v9kv5b` 안경박사 본점 — 안경박사는 1997년에 시작된 브랜드로, 한국 안경 유통에 변화를 일으켰습니다. 고객 맞춤형 피팅 서비스로 유명하며, 1년 만에 100호점을 돌파했습니다. 본점은 성북구 역사와 자연이 어우러진 정릉동에 위치해 있기에, 안경점에서 안경을 맞춘 뒤, 더 밝아진 눈으로 정릉의 아름다운 풍경을 즐길 수 있습니다.
  - `tw1dyr` 박선영전통한복연구실 — 박선영전통한복연구실은 전통 한복의 정수를 담고 있는 곳으로, 이곳은 서울시무형문화재 제11호 침선장 박선영 장인이 한복의 아름다움과 그 속에 깃든 조상의 얼을 지키기 위해 시작되었습니다. 현재 이곳은 침선장 박선영 장인의 기술을 이어받은 그녀의 아들 김기상씨가 이어받아 운영하고 있습니다. 고객은 다양한 색감의 고급 원단 
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID corresponds uniquely to Calvin Klein, which offers the specified products and multilingual staff.

## augmentation-v1-013 — excluded_constraint → train

- Question: 어떤 매장에서 캘빈클라인의 다양한 상품을 경험하고 쇼핑할 수 있나요?
- Expected IDs: ennz8o
- Candidates:
  - `ennz8o` 캘빈클라인 명동점 — Calvin Klein은 대담하고 진보적인 이상과 매혹적인 미학을 보여주는 글로벌 라이프스타일 브랜드입니다. 캘빈클라인 명동점은 캘빈클라인 진, 언더웨어, 액세서리 등 캘빈클라인에서 전개하는 모든 상품을 경험하고 쇼핑 할 수 있는 Combo Store 입니다. 매장에서 방문하셔서 캘빈클라인의 매력적인 상품들을 만나보세요.
  - `jxvczp` 플레이인더박스 더현대서울점 (excluded) — 플레이인더박스는 MZ들의 성지이자 재미와 즐거움이 넘치는 공간으로, 다양한 캐릭터, 브랜드를 경험할 수 있는 플랫폼입니다. 전 세계적으로 유명한 캐릭터 굿즈, SNS에서만 보던 개성 넘치는 소품들부터 네컷사진, 캡슐토이, 포토존, 팝업스토어, ASMR 등 다양한 컨텐츠를 경험해 볼 수 있습니다. 캐릭터들과의 협업을 통해 
  - `h102m6` 스토리지북앤필름 로터리점 — 스토리지북앤필름 로터리점은 후암동 108계단에 자리잡은 작은 책방으로 책과 함께 필름을 판매합니다. 독립출판과 소규모출판물을 다루는 독립서점으로 다른지점과 5분 거리에 위치해있습니다. 일반 서점에서는 만나볼 수 없는 다양한 분야의 책들이 소개되어 있고, 벽면에는 책과 관련된 굿즈 등 굿즈들이 알차게 준비되어 있어 구경하기
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 'ennz8o' is uniquely supported by the provided evidence, which describes the Calvin Klein Myeongdong store as a place to experience and shop for various Calvin Klein products.

## augmentation-v1-014 — excluded_constraint → train

- Question: What type of bookstore focuses on literature and hosts events related to reading and writing?
- Expected IDs: wnlgos
- Candidates:
  - `wnlgos` 고요서사 — 남산 아래 해방촌에 위치한 작은 서점으로 2015년 가을에 문을 열었습니다. 소설과 시, 에세이로 서가의 중심을 채우는 '문학 중심 서점'을 지향하는 서점입니다. 문학에서 주요하게 다루는 가치나 주제들, 예를 들어 인권, 젠더, 역사적 사건, 대안적 삶 등과 연관된 인문, 사회, 예술 책도 함께 소개하여 풍성한 독서의 길
  - `4g7mm3` 가정식 패브릭 (excluded) — 가정식 패브릭은 정동길 신아기념관에 위치한 의류 브랜드 쇼룸입니 다. 자연과 가까운 소재들을 수집해 자연스럽고 편안한 옷을 만드는 것이 브랜드의 목표입니다. 아늑한 공간에서 자연과 어울리는 옷들을 구경할 수 있습니다. 시기에 맞는 전시가 종종 열려 다양한 작품들을 구경할 수 있는데 유리공예에서부터 자수공예, 라탄공예, 펠
  - `27a0mo` 쥬얼파크 — 남대문 시장에 위치한 귀금속 매장으로 다양한 브랜드들이 입점해있습니다. 도매 전문 매장으로 악세사리를 만들 수 있는 부자재나 여러종류의 악세서리를 구입 할 수 있습니다. 또한 도매매장이다보니 최소 구매수량, 사입 단가, 소재 등을 확인해야 한다는 특이사항이 있습니다. 2030 여성이 사용하는 실버 주얼리 제품들을 파는 상
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place 'wnlgos' is uniquely supported by the evidence as a literature-focused bookstore that hosts events related to reading and writing.

## augmentation-v1-015 — excluded_constraint → dev

- Question: 어린이 의류를 저렴한 가격에 직접 보고 구매할 수 있는 매장은 어디인가요?
- Expected IDs: lm37m4
- Candidates:
  - `lm37m4` 부르뎅아동복 — 35년동안 운영중인 남대문에 위치한 아동복 매장입니다. 전체 회원사들이 각각 고유한 디자인팀을 가동하여 직접 생산 및 판매하는 제조소매업상가입니다. 비교적 저렴한 가격으로 아동복을 판매하고 있습니다. 남대문시장을 비롯해 다양한 매체 및 지자체로부터 최우수상가로 선정되어 영아부터 유아, 어린이까지의 옷을 파는 브랜드들이 모
  - `l4du7k` 포키아동복 (excluded) — 1975년에 개장한 남대문 최대의 아동복 매장으로 지금까지 그 명성을 유지하며 좋은 품질의 옷을 비교적 저렴한 가격으로 판매하고 있습니다. 많은 브랜드들이 모여있는 상가로 어린이집, 유치원 등원복, 실내복, 신생아 용품 뿐만 아니라 양말, 모자 등 악세사리까지 다양하게 준비되어 있습니다. 낮 시간대에는 소매, 야간에는 도
  - `rrfib6` 미스테리우스 — 미스테리우스는 해피투게더 타투샵의 공식 굿즈 샵으로 해피투게더 스튜디오 소속 아티스트의 각종 굿즈와 커스텀 타투 배너, 플래쉬, 빈티지, 식물 등 다양한 오브젝트를 함께 만나볼 수 있는 공간입니다. 진열되어 있는 소품들도 어디서도 볼 수 없던 분위기의 소품들이 잔뜩 나열되어 있습니다. 또한 몇몇 굿즈들의 디자인은 직접 그
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 'lm37m4' is uniquely supported by the evidence, which describes a children's clothing store offering affordable prices and the ability to inspect items in person.

## augmentation-v1-016 — excluded_constraint → train

- Question: What lifestyle beauty brand offers a flagship store where customers can experience perfumes and body care products, and has received praise for its excellent customer service?
- Expected IDs: 0gxkdq
- Candidates:
  - `0gxkdq` 논픽션 한남 — 논픽션은 자신의 가장 솔직한 모습과 마주하는 시간을 위해 탄생한 라이프스타일 뷰티 브랜드입니다. 최상의 원료와 섬세한 조향을 바탕으로 신비롭고 독특한 무드를 빚어내는 향수, 하루의 시작과 끝을 더욱 정성스럽게 만드는 바디케어 제품군을 선보입니다. 논픽션 한남은 라이프 스타일 뷰티 브랜드로 향수와 핸드크림 등을 쇼핑할 수 
  - `43to2h` 스토리지북앤필름 storage book and film (excluded) — 2008년 카메라스토리지로 시작하여, 2012년부터는 독립책방으로 운영되고 있습니다. 주로 소규모 출판물을 소개 및 판매하며, 자체 출판물들도 제작합니다. 2013년부터 2019년까지 독립출판물 페어 <퍼블리셔스테이블>을 만들고 운영했으며, 현재는 <리틀프레스페어>를 주최, 진행, 운영하고 있습니다. 2016년부터 독립출
  - `z1lgm9` 지구불시착 — 오랫동안 마을순환경제의 거점공간인 ‘마을과 마디’와 함께 했던 독립서점 ‘지구불시착’ 에서는 다양한 주제의 독립서적들이 구비되어 되어있습니다. 이 서점에서는 사장님이 그린 특색있는 굿즈들도 구경할 수 있으며 즉석 30초 초상화도 그려줄 수 있다고 합니다. 또한 책방지기가 직접 그리고 만든 그림책과 노트 등 문구, 독립출판
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID '0gxkdq' is uniquely supported by the evidence, which describes a lifestyle beauty brand flagship store offering perfumes and body care products with excellent customer service.

## augmentation-v1-017 — excluded_constraint → train

- Question: 어디에서 재정비된 중고 의류와 빈티지 아이템을 다양하게 구경하며 나의 스타일에 맞는 제품을 고를 수 있나요?
- Expected IDs: rzx6dz
- Candidates:
  - `rzx6dz` 리뉴드 성수 — 리뉴드 성수는 모바일 간편 의류 수거 '리클'에서 운영하는 빈티지숍입니다. 매장 안에는 재정비된 중고 의류, 빈티지 아이템, 옛날 액세서리들이 다양하게 모여 있습니다. 깔끔하게 정리된 빈티지 제품들 속에서 오랜 시간 천천히 돌아보며 나의 스타일에 맞는 제품을 고르는 재미를 느껴보세요.
  - `g1mnzj` 황학동 만물 시장 (excluded) — 황학동 만물시장은 한국전쟁 이후 삶의 터전을 잃은 이들이 미군 부대에서 흘러나온 물품을 팔던 '도깨비 시장'에서 출발했습니다. 세월이 흐르며 단순한 중고품 거래를 넘어, 고물과 골동품, 단종된 생활용품까지 아우르는 '만물시장'으로 자랐습니다. 오래된 간판의 골동품 가게는 사지 않아도 자유롭게 들어가 볼 수 있습니다.
  - `64f1uy` 양재꽃시장 — 양재 꽃 시장은 1991년 시작된 한국 최대 꽃 시장이며, 대형 화훼단지로 도매 거래뿐만 아니라 소규모 거래도 가능하니 꽃을 좋아하는 누구나 방문해보길 추천합니다. 생화, 분화 온실, 나무 시장과 관련 자재 시장이 있는 공판장과 꽃 문화 체험관인 F 스퀘어로 나뉘어 있습니다. 농립축산식품부와 aT한국농수산식품유통공사가 함
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place '리뉴드 성수' is uniquely supported by the provided evidence, which describes it as a vintage shop with a variety of secondhand clothing and vintage items.

## augmentation-v1-018 — excluded_constraint → train

- Question: What shopping area is known for its concentration of fashion and beauty stores, reflecting the latest trends like Y2K fashion and balletcore, and is popular among young people and tourists?
- Expected IDs: c8w958
- Candidates:
  - `c8w958` 홍대R3 패션거리 — R3 구역은 패션과 쇼핑의 중심지로, 다양한 의류 및 화장품 매장이 밀집해 있습니다. 최근에는 Y2K 패션, 발레코어 등 최신 트렌드를 반영한 아이템을 판매하는 상점들이 늘어나면서 홍대패션의 감각이 완성되는 곳입니다. SNS에서 유명한 가게들이 많이 위치하고 있어 젊은 층과 관광객들에게 큰 인기를 끌고 있습니다.
  - `ue1dn6` 소품공장 (excluded) — 10, 15, 20cm 사이즈 별 인형과 인형 옷, 인형 소품을 판매하는 소품샵으로 동물 옷부터 한복, 아이돌 무대 의상까지 다양한 컨셉의 인형 옷을 볼 수 있습니다. 실제 매장에서 옷을 구매하듯 코디가 된 의상을 보며 인형 옷을 고를 수 있으며, 구매한 인형 옷을 입히고 여러 컨셉의 포토존에서 인형을 올려놓고 사진을 찍
  - `veuat2` 더키월드 — 홍대에서 K-POP 굿즈샵을 둘러보았다면 마지막으로 더키월드에 방문해 아이돌 굿즈를 보관할 수 있는 포카홀더, 콜렉트북, 인형파우치, 탑로더, 슬리브 등을 구매 할 수 있습니다. 깔끔하게 포토카드 콜렉트북, 탑로더에 보관 하거나 귀여운 그림이나 글씨가 적혀 있는 포카홀더에 넣어 언제 어디서나 소장할 수 있습니다.
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 'c8w958' is uniquely supported by the evidence, which describes it as a fashion and shopping hub popular for trends like Y2K fashion and balletcore.

## augmentation-v1-019 — excluded_constraint → train

- Question: 어떤 장소는 K-POP 팬들에게 필수 코스이며, 포토카드 자판기에서 랜덤으로 포토카드를 뽑는 재미를 제공하나요?
- Expected IDs: di0px1
- Candidates:
  - `di0px1` 포카부 — K-POP을 좋아하는 사람이라면 놓칠 수 없는 포토카드 매장이며, 포토카드 수집가들에게는 필수 코스라고 할 수 있는 곳입니다. K-POP을 좋아하는 외국인들에게도 인기 있는 핫플레이스로 외국인들을 위한 영어 설명도 볼 수 있습니다. 포토카드 자판기에서 최애 아티스트의 포토카드를 랜덤으로 뽑는 재미도 느껴보시길 바랍니다.
  - `7xadww` 공릉동 도깨비시장 (excluded) — 공릉동 도깨비 시장은 1939년 7월 25일 경춘철도가 개통되면서 화랑대역 인근에 모여든 노점상으로부터 비롯되었습니다. 노점 단속이 나오면 도깨비가 다녀간 듯 순식간에 사라지고, 단속이 끝나면 다시 옹기종기 철길에 모여 장터를 꾸려나가던 재래도깨비시장이 현재 공릉동도깨비시장의 시초입니다. 이후로는 도깨비방망이로 뚝딱한 듯
  - `038195` 서울 중앙시장 — 서울의 많은 전통시장 중 하나인 서울 중앙시장은 한국전쟁 이후로 한국의 3대 시장으로 꼽힐 만큼 많은 거래와 소비가 이루어지던 시장입니다. 현재도 다양한 먹거리와 볼거리가 있어 근처의 동묘와 함께 많은 사람들의 사랑을 받고 있는 장소입니다. 곳곳의 옛 감성이 담긴 시장의 골목 풍경과 싱싱한 해산물, 반찬거리, 분식 꽈배기
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place '포카부' is uniquely supported by the evidence, describing it as a must-visit for K-POP fans with photocard vending machines.

## augmentation-v1-020 — excluded_constraint → dev

- Question: What market, established in 1953, is known for its unique atmosphere created by a blend of diverse cultures and offers a variety of food options including chicken, sushi, and Thai cuisine?
- Expected IDs: 037951
- Candidates:
  - `037951` 신흥시장 — 1953년 해방 이후부터 해방촌 시장의 이름을 갖게 된 신흥시장은 70년 동안 운영되어 다양한 국적과 문화를 지닌 사람들이 함께 어우러져 이곳만의 특별한 분위기를 만들어왔습니다. 신흥시장은 대표적인 시장의 이미지가 아닌 과거와 현재가 공존하는 이국적인 분위기를 자아내 많은 사람들의 관심을 받고 있는 곳입니다. 치킨, 횟집
  - `031984` 제일시장 (excluded) — 1970년에 개장한 제일시장은 의류, 생활용품, 반찬, 음식 등을 판매하는 70여 곳의 상점이 모여 있습니다. 시장 안쪽으로 10여 곳의 분식점이 자리 잡고 있으며, 납작만두와 순댓국이 유명합니다.
  - `031944` 증산종합시장  — 증산종합시장은 농축산물, 수산물, 건어물 등의식재료와 철물, 음식점 등 180여 개 점포가 하나의 상가 건물 안에 자리잡은 시장입니다. 먹거리로 30년 넘은 순댓국이 유명하며, 시장 중앙에 10여 곳의 음식점이 자리하고 있습니다. 2017년 주민참여예산사업으로 청년 지원 사업이 선정되어 ‘꽃차 러브포션’, ‘형제술집’ 등
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 037951 is uniquely supported by the evidence, which describes Shinheung Market established in 1953, known for its diverse food options including chicken, sushi, and Thai cuisine.

## augmentation-v1-021 — context_grounded → train

- Question: 어떤 시장이 족발로 유명하며 다양한 맛집이 있는 재래시장인가요?
- Expected IDs: 028335
- Candidates:
  - `028335` 공덕시장 — 공덕시장은 공덕역 인근 족발로 유명한 재래시장입니다. 족발집을 비롯해 전집, 고깃집 등 다양한 맛집으로 이루어져 있습니다. 족발골목 전골목
  - `001356` 서울약령시장 — 서울약령시장은 국내 최대의 한의약 종합 단지로, 800여 개가 넘는 한약 관련 점포를 확보하고 있습니다. 전국의 약재란 약재는 모두 이곳에 모입니다. 서울약령시장은 1960년대 한약재 상인들이 전국에서 청량리역을 이용해 모여들기 시작하며 자연발생적으로 생겨난 것입니다. 이곳에서는 각종 민간 요법에 등장하는 개구리, 자라,
  - `000281` 통인시장 — 세종마을은 추사 김정희 등 조선시대 예능인들이 모이는 중심지였으며 근대에도 이상 등 문인들이 활동하던 중심지였습니다. 일제강점기 일본인들을 위해 만들어진 공설시장이 모태이나 6.25이후 인구증가로 시장의 필요성이 높아져 현재처럼 물건을 사고파는 시장의 형태를 갖추게 되었습니다. 통인시장은 상권이 활성화된 곳으로 다른 전통
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 028335 is uniquely supported by the evidence, confirming Gongdeok Market's fame for Jokbal and its variety of eateries.

## augmentation-v1-022 — context_grounded → train

- Question: What market is known for selling a large variety of fabrics, accessories, and handmade items, and is a popular destination for shoppers looking for unique materials and courses?
- Expected IDs: 000170
- Candidates:
  - `000170` 동대문 종합시장 — 1970년생인 동대문 종합시장은 동대문시장과 40여 년 동안 희로애락을 함께한 터줏대감입니다. 동대문 종합시장은 의류 재료인 원단부터 의류 부자재, 액세서리 등과 일부 혼수용품을 파는 대규모 전문 시장입니다. 국내 시장에서 거래되는 원단의 80%가 이곳을 거쳐갑니다. 동대문 종합시장엔 아직도 여전히 옛 정서, 옛 풍경을 
  - `000085` 남대문시장 — 남대문시장은 하루 50만 명이 찾는 거대한 유통 공간으로 우리나라 최고, 최대 재래시장입니다. 조선중기부터 저잣 거리로 자리잡은 남대문 시장은 역사가 오래된 만큼 규모도 대단하고 취급품도 다양합니다. 대도레이디, 대도, 퀸프라자, 장띠모아 등에서는 성인 남녀 의류의 모든 것을 만날 수 있습니다. 아동복 상가는 전국 아동복
  - `009646` 동묘 벼룩시장 — 동묘 벼룩시장은 1980년대 말 생겨났으며 명성에 비하면 그 규모가 많이 위축됐지만 지금도 온갖 희귀한 물건들이 모여드는 입니다. 의류, 신발, 지갑부터 시계나 전자제품, 심지어 고서, 영화 포스터에 이르기까지 온갖 제품들을 망라하고 있습니다. 이곳의 물건은 대부분 1,000원으로, 거의 공짜라는 생각이 들 정도입니다. 
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID '000170' corresponds to Dongdaemun Shopping Complex, which is uniquely supported by the provided evidence as a market known for selling a large variety of fabrics, accessories, and handmade items.

## augmentation-v1-023 — context_grounded → train

- Question: 어디에서 200여 개의 업소가 모여 다양한 먹거리를 제공하며, 떡볶이 1인분이 2500원인 시장은 어디인가요?
- Expected IDs: 009547
- Candidates:
  - `009547` 숭인시장 — 미아거리 전철역을 나오면 곧장 숭인시장으로 이어지는 입구가 보입니다. 인근의 백화점 틈에서도 숭인시장은 그 동네에서 수십 년을 살아온 토박이처럼 뚝심 있게 자리를 지키고 있습니다. 숭인시장은 지난 2003년에 환경 정비 사업을 통해 재래시장의 매력은 살리되 재래시장의 불편함은 줄였습니다. 시장에는 의류 코너, 전통 공예품
  - `009505` 노량진 수산시장 — 바다와 동떨어진 서울 시내 한복판에서 바다를 만날 수 있는 곳. 바로 지하철 1·9호선 노량진역에 위치한 노량진 수산시장입니다. 전국의 각종 수산물이 이곳에 모여 경매 방식을 통해 전국 각 시장으로 운송됩니다. 각 산지의 수산물이 한곳에 모이는 것입니다. 바다를 볼 수 없는 서울 시민들에게 노량진 수산시장은 바다의 맛을 
  - `v4bofj` 감사의 정원 — 광화문광장에 새롭게 조성된 감사의 정원은 6 ·25 전쟁 참전용사에 대한 감사와, 도움 받던 나라에서 도움을 드리는 나라로 도약한 대한민국의 성과와 번영을 되새기는 공간입니다. 감사의 빛 23은 광화문광장의 중심에 고요하면서도 웅장하게 자리 잡은 23개의 상징조형물으로, 대한민국의 자유와 평화를 수호하기 위해 기꺼이 손을
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): Expected place is uniquely supported by the evidence.

## augmentation-v1-024 — context_grounded → train

- Question: What historical site was primarily used as a library and a place for receiving foreign envoys, and is now open to the public as a library since 2016?
- Expected IDs: fk9nxi
- Candidates:
  - `fk9nxi` 경복궁 집옥재 — 경복궁 건천궁 서쪽에 위치한 전각입니다. 청나라에서 구매한 서양 문물 관련 4만 여 권의 서적들이 이곳에 보관되었고 고종의 서재로 주로 사용되었습니다. 이외에도 어진을 모시거나 외국 사신들을 접견하는 장소로 활용되었습니다. 과거에는 창덕궁 함녕전의 별당으로 지어졌으나 1891년에 경복궁으로 이전되었습니다. 2006년부터 
  - `ldz98j` 경복궁 돌담길  — 경복궁 돌담길은 경복궁을 둘러싸고 있는 돌담길입니다. 광화문을 중심으로 좌측으로는 경복궁의 서문인 영추문, 북쪽으로는 북문인 신무문, 우측으로는 동문인 건춘문을 중심으로 둘러쌓여 있습니다. 경복궁 돌담길의 좌측으로는 서촌과 연결되어 있고 북쪽으로는 청와대와 연결되어 있습니다. 오른쪽은 북촌과 삼청동으로 연결되어 있어 국립
  - `jkm9y3` 신아기념관 — 정동에 위치한 특이하게 쌓여진 붉은 벽돌이 인상적인 건물로, 1930년대 지하 1층, 지상 2층으로 건축된 철근콘크리트 건물입니다. 100년이라는 세월을 건물 속에 구조와 마감, 설비들을 통해 알수 있습니다. 국내 최초로 판매된 미국 미싱 브랜드 '싱거미싱' 회사 한국지부로 사용되다가 1963년 한국 최초의 상업신문이었던
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 'fk9nxi' is uniquely supported by the evidence, which describes its historical use as a library and a venue for receiving foreign envoys, and confirms its opening to the public as a library in 2016.

## augmentation-v1-025 — context_grounded → train

- Question: 어떤 공간이 독립운동가들의 얼을 기리기 위해 조성되었으며, 관리동과 전시동으로 이루어져 있습니까?
- Expected IDs: 041904
- Candidates:
  - `041904` 중랑망우공간 — 오랫동안 공동묘지로 사용되었던 망우리가 유관순, 한용운, 안창호, 방정환 등 독립운동가들의 얼을 기리기 위한 '망우역사문화공원'으로 재탄생했습니다. 그 속에 위치한 '중랑망우공간'은 망우산의 고요한 자연을 거닐며 위인들의 숭고한 뜻을 기릴 수 있도록 새롭게 조성된 공간입니다. 중랑망우공간은 크게 관리동과 전시동의 두 건물
  - `039629` 춘당지 — 창경궁 뒤뜰에서는 아름다운 춘당지를 만나 볼 수 있습니다. 북악산에서 흘러 내려온 물이 모여 연못이 되어 춘당지가 되었습니다. 작은 연못을 소춘당지라고 하고, 큰 연못을 대춘당지라 하는데 지금의 대춘당지는 1984년 창경궁이 복원되면서 한국식 정원으로 바뀌었다고 합니다. 특히 궁의 고즈넉한 분위기와 잔잔한 연못 위에 비추
  - `023758` 소덕문 터(옛 서소문) — 소덕문은 도성의 서남쪽인 숭례문과 돈의문의 중간지점에 있었습니다. 도성의 4개의 소문(小門) 중 하나로서 태조 5년에 다른 성문들과 함께 건설되었습니다. 일제 때인 1914년 도시 계획이라는 구실로 철거되었고 지금은 그 흔적을 찾아볼 수 없습니다.
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 041904 is uniquely supported by the provided evidence, which describes the space dedicated to honoring independence activists and mentions its management and exhibition buildings.

## augmentation-v1-026 — context_grounded → dev

- Question: What historical gate was built in 1719 and is known for its unique architecture and historical significance in the context of the city's past?
- Expected IDs: 023605
- Candidates:
  - `023605` 광희문 — 시구문(屍軀門) ·수구문(水口門)이라고도 하였으며 서소문(西小門)과 함께 시신(屍身)을 내보내던 문입니다. 1719년 문루를 세워서 광희문이라는 현판을 걸었습니다. 그 후 1975년 도성복원공사의 일환으로 석문을 수리하고 문루를 재건하였습니다.
  - `022888` 숭례문(남대문) — 서울 도성의 남쪽 정문이라서 통칭 남대문(南大門)이라고 불립니다. 1395년(태조 4)에 짓기 시작하여 1398년(태조 7)에 완성되었고, 1447년(세종 29)에 개축하였습니다. 이 문은 중앙부에 홍예문(虹 蜺 門)을 낸 거대한 석축기단 위에 섰으며, 현존하는 한국 성문 건물로서는 가장 규모가 큽니다. 1962년 12월
  - `015109` 고궁을 찾다 — 조선시대의 궁궐이 다섯 개 남아 방문객들에게 과거 궁중에서의 삶에 대해 짐작하게 해줍니다. 광활한 경복궁부터 감춰진 아름다운 정원이 있는 창덕궁, 좀 더 작고 아늑한 운현궁까지, 궁궐들은 역사를 보전하는데 큰 몫을 하고 있습니다. <관련 콘텐츠 정보 보기> 경복궁 창덕궁 창경궁
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID 023605 corresponds to Gwanghuimun Gate, which was built in 1719 and is known for its unique architecture and historical significance.

## augmentation-v1-027 — context_grounded → train

- Question: 이곳은 조선 태조 7년에 완공된 역사적인 성문으로, 현재는 도로 가운데 성문만 남아 있으며, 밤에 방문하면 아름다운 불빛을 감상할 수 있는 장소는 어디인가요?
- Expected IDs: 001999
- Candidates:
  - `001999` 흥인지문(동대문) — 보물 제1호 흥인지문(興仁之門)은 한성부를 보호하기 위해 만든 서울 성곽의 여덟 성문 가운데 동쪽의 큰 대문에 해당합니다. 동대문이라는 이름도 거기서 기인했습니다. 조선 태조 7년(1398)에 완성되었고 고종 6년(1869)에 개보수되었습니다. 흥인지문은 중앙에 홍예문을 두고 정면 5칸, 측면 2칸의 중층문루를 세워 지은
  - `001159` 경희궁 — 경희궁은 본래 인조의 아버지인 정원군의 집이었으나, 그 터에 왕기가 서려 있다는 말이 돌자 광해군이 이를 몰수해 궁궐을 지었습니다. 건립 당시만 1500칸에 이르는 대궐이었던 경희궁은 일제강점기를 거치며 가장 철저하게 파괴됐습니다. 일사늑약(을사조약)이 강제 체결되고 경성중학교가 들어서면서부터입니다. 또한 경희궁 터에는 
  - `000507` 종묘 — 왕의 위패를 모시고 제를 올리는 종묘는 조선의 역사에 더없이 중요한 장소였습니다. 임금이 새로 왕위에 오르면 가장 먼저 종묘와 사직에 나아가 절을 하며 제사를 드렸습니다. 종묘는 단순한 구조의 재실을 길게 연결해 장엄한 엄숙미를 연출합니다. 이곳에서 지내는 제사인 종묘대제(宗廟大祭)는 삼국 시대부터 있었던 국가적인 행사로
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID '001999' (흥인지문) is uniquely supported by the provided evidence, which describes its historical significance, completion date, and the beauty of its night illumination.

## augmentation-v1-028 — context_grounded → train

- Question: What historical site served as the residence of a prominent figure during the late Joseon Dynasty and was the birthplace of a future king, where significant reforms were initiated?
- Expected IDs: 000471
- Candidates:
  - `000471` 운현궁  — 운현궁은 조선 후기 흥선대원군의 사가입니다. 흥선대원군의 둘째 아들 고종이 출생하여 왕위에 오르기 전까지 성장한 곳입니다. 이곳에서 대원군은 서원철폐, 경복궁 중건, 세제개혁 등 많은 사업을 추진하였습니다. 흥선대원군의 한옥과 양관(洋館)은 모두 사적으로 지정되어있습니다.
  - `000297` 창경궁 — 창경궁은 1483년 창덕궁 동쪽에 세워진 궁으로, 성종이 정희왕후, 안순왕후, 소혜왕후를 위해 수강궁을 확장하면서 창경궁이라는 이름을 붙였습니다. 명정전과 문정전, 환경전, 경춘전 등 대부분의 전각이 이때 지어졌습니다. 창경궁은 아픈 역사가 깃든 궁이기도 합니다. 1911년 일제에 의해 창경원으로 격하됐고 동물원과 식물원
  - `000295` 창덕궁 — 창덕궁은 서울에서 두 번째로 유네스코 선정 세계문화유산으로 등재되었습니다. ‘동아시아 궁전 건축사에 있어 비정형적 조형미를 간직한 대표적 궁으로 주변 자연환경과의 완벽한 조화와 배치가 탁월하다’는 이유로 선정됐습니다. 창덕궁은 1405년 태종에 의해 건립되었으며, 오랜 시간 법궁(法宮)의 역할을 한 궁궐입니다. 조선은 임
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): The expected place ID '000471' corresponds to Unhyeongung Palace, which is accurately described as the residence of Heungseon Daewongun and the birthplace of Emperor Gojong, where significant reforms were initiated.

## augmentation-v1-029 — no_result → train

- Question: 모든 후보가 조건과 충돌하면 추천할 곳이 없다고 알려줘
- Expected IDs: (none)
- Candidates:
  - `000072` 경복궁 (excluded) — 경복궁은 조선 시대에 지어진 왕궁 중 가장 큰 궁궐이었습니다. 조선 왕조 개국 3년인 1395년에 창건된 궁궐은 390여 칸으로 한양의 중심축에 자리했습니다. 개국공신 정도전은 태조로부터 첫 번째 궁궐의 이름을 지으라는 명을 받았고, 고심 끝에 '새 왕조가 큰 복을 누려 번영할 것'이라는 의미로 경복궁(景福宮)이라는 이름
  - `kxi16h` 경국사  (excluded) — 삼각산(현 북한산) 동쪽 기슭에 자리잡은 경국사는 고려 말에 창건된 오래된 사찰입니다. 주변 산세가 좋고 약수가 있어 많은 사람들이 찾아오는 곳입니다. 경국사는 극락보전, 영산전, 명부전, 관음전, 시방선원 등 17동의 건물으로 이루어져 있습니다. 그 중 극락보전에는 아미타삼존불을 비롯하여 보물 제748호로 지정된 목각탱
  - `029394` 절두산순교성지 (excluded) — 1866년 병인박해 때 순교한 천주교인의 신앙과 얼을 널리 알리기 위하여 서울 마포구에 1967년 10월 절두산순교기념관으로 개관한 뒤 한국천주교순교자박물관으로 이름을 바꾸었습니다. 박물관 시설은 순례성당, 순교성인의 유해를 모신 성해실, 한국천주교회사 관련 사료와 유물·유품 등이 전시되어 있는 박물관, 야외전시장으로 이
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): All candidates exist in DB and each has an explicit conflict constraint.

## augmentation-v1-030 — no_result → train

- Question: Say there is no match if every candidate conflicts with the condition.
- Expected IDs: (none)
- Candidates:
  - `028339` 봉원사 (excluded) — 봉원사는 신라 진성여왕 3년(889년)에 현 연세대 터에 창건한 절로, 조선 영조 24년(1748년) 때 지금의 터전으로 이전했습니다. 마당엔 수조에 빼곡하게 심어놓은 연꽃이 가득해 특히 여름이면 큼지막한 연꽃과 어우러진 독특한 절 풍경을 축제와 함께 즐길 수 있습니다. 마음을 정화하고 싶을 때 힐링하기 딱 좋은 곳입니다
  - `001153` 양화진외국인선교사묘원 (excluded) — 양화진외국인선교사묘원은 서울 마포구 합정동에 위치한 외국인 선교사들의 공동묘지입니다. 한국을 사랑하고 한국에 묻히기를 원했던 외국인 선교사들과 그 가족의 안식처입니다. 한국기독교 선교 100주년기념교회가 관리하고 있으며 한국선교기념관이 설립되어 있습니다.
  - `004863` 서울중앙성원 (excluded) — 서울 용산구 한남동에 위치한 서울 중앙 성원은 1969년 5월 한국정부의 특별배려에 따라 약 1,500평의 성원건립 부지를 마련해주고 사우디아라비아를 비롯한 전세계 이슬람국가들이 성원건립 비용을 지원하며 1974년 10월 착공, 1976년 5월 21일에 개원한 한국 최초의 이슬람 성원입니다. 한강과 남산의 중간지점에 자리
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): All candidates exist in DB and each has an explicit conflict constraint.

## augmentation-v1-031 — no_result → dev

- Question: 모든 후보가 조건과 충돌하면 추천할 곳이 없다고 알려줘
- Expected IDs: (none)
- Candidates:
  - `004036` 명동성당 (excluded) — 명동성당은 우리나라 최초의 본당이며 한국 천주교회의 상징입니다. 고종 29년(1892)에 착공, 광무 2년(1898)에 준공되었습니다. 명동성당은 우리나라 기독교 역사뿐 아니라 정치, 사회, 문화 전반에 걸쳐 큰 영향을 미친 터전입니다. 개발 독재의 서슬이 퍼렇던 1970년대 이후 시대의 요구와 아픔, 민중의 눈물을 품어
  - `002010` 안동교회 소허당 (excluded) — 안동교회는 서울 종로구 안국동에 위치한 장로교회입니다. 당시의 교회들은 서양선교사들의 주도로 지어졌으나 안동교회는 한국인들에 의해 북촌 양반마을에서 시작되었다는 점에서 의의가 있습니다. 소허당은 안동교회에서 운영하는 휴식공간으로 무료로 차를 제공하고 있습니다 .
  - `001862` 원효로성당 (excluded) — 원효로성당은 서울 용산구 원효로에 위치해 있으며 서울 용산신학교와 나란히 세워져 있습니다. 서울 용산신학교의 부속성당이며 프랑스 고딕풍 건축물로 한국 근대식 성당입니다. 규모는 작으나 단단하고 균형 잡힌 모습을 갖추고 있습니다.
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): All candidates exist in DB and each has an explicit conflict constraint.

## augmentation-v1-032 — no_result → train

- Question: Say there is no match if every candidate conflicts with the condition.
- Expected IDs: (none)
- Candidates:
  - `003255` 길상사 (excluded) — 성북동의 복잡한 다운타운을 뚫고 들어가면 길상사가 보입니다. 정문을 지나면 기둥과 서까래가 그대로 보이는 기와집 한 채가 서 있습니다. 대웅전 격인 극락전입니다. 죽은 이의 극락왕생을 비는 지장전은 범종각과 함께 사찰 기능을 보완하려는 차원에서 새로 지은 건물이지만 한국 전통 미를 그대로 간직하고 있습니다. 일반적인 절과
  - `002586` 조계사 (excluded) — 조계사는 1910년, 조선불교의 자주화와 민족자본 회복을 염원하는 스님들에 의해 각황사란 이름으로 창건되었습니다. 당시 각황사는 4대문 안에 최초로 자리 잡은 사찰이었습니다. 1937년에 각황사를 현재의 조계사로 옮기는 공사를 시작했고 현재의 조계사는 서울의 도심인 종로 한가운데 위치한 유일한 전통 사찰로서, 휴식과 여유
  - `001776` 국립 4.19민주묘지 (excluded) — 북한산을 배경으로 한 4·19 민주묘지는 4·19 혁명 때 희생된 분들의 합동분묘로서 , 이들을 기리는 기념탑이세워져 있고 , 전시공간인 4.19 혁명 기념관이 자리 잡고있습니다 . 4·19 혁명은 민주주의에 대한 열망을 그대로 드러낸 일대 사건으로 이때 목숨을 잃은 185 명의 영혼이 이곳에 고이 안장되어 있습니다 . 
- Review decision: `reviewed`
- Review note: DB fact check (reviewed): All candidates exist in DB and each has an explicit conflict constraint.
