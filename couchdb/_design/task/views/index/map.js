function(doc) {
	var toemit=[];
	var s = doc.summary.match(/[^\W_]+/g);
	for (var i =0;i<s.length;i++) {
	        var toem = s[i].toLowerCase();
                if (toemit.indexOf(toem)==-1)
			toemit.push(toem);
	}
	for (var i=0;i<toemit.length;i++)
		emit(toemit[i],doc._id);
}